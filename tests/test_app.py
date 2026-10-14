"""The app as the server runs it: started on a free port, called like nginx calls it.

    uv run python -m unittest discover -s tests

needs nothing more than the app does: the tests use Python's own tools.
"""
import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Answer:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.text = status, headers, body.decode()

    def json(self):
        return json.loads(self.text)


class Running:
    """The app, started with these environment variables. Ready once it answers /health."""

    def __init__(self, **env):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(self.port), "--log-config", "logging.json"],
            cwd=ROOT, env={**os.environ, "DEV": "", "SIGNIN": "", "APP_NAME": "", **env}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(100):
            try:
                if self.call("/health").status == 200:
                    return
            except OSError:
                time.sleep(0.1)
        self.stop()
        raise RuntimeError("The app did not start. Try it by hand: uv run dev.py")

    def call(self, path, method="GET", headers=None, body=None) -> Answer:
        request = urllib.request.Request(self.base + path, method=method, headers=headers or {}, data=body.encode() if body is not None else None)
        try:
            with urllib.request.urlopen(request, timeout=10) as r:
                return Answer(r.status, r.headers, r.read())
        except urllib.error.HTTPError as e:
            return Answer(e.code, e.headers, e.read())

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(5)
        except subprocess.TimeoutExpired:
            self.process.kill()


def as_user(user: str, groups: list[str]) -> dict:
    """What nginx adds after the sign-in."""
    return {"Remote-User": user, "Remote-Name": user.upper(), "Remote-Email": f"{user}@example.com", "Remote-Groups": ",".join(groups)}


CHANGE = {"X-Requested-By": "app", "Content-Type": "application/json"}


class BehindTheSignIn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Running(APP_NAME="Test app")

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def test_health_answers_without_a_sign_in(self):
        r = self.app.call("/health")
        self.assertEqual((r.status, r.text), (200, "ok\n"))

    def test_who_is_signed_in_and_nothing_without_it(self):
        me = self.app.call("/api/me", headers=as_user("lea", ["friends", "qa"])).json()
        self.assertEqual(me["app"], "Test app")
        self.assertEqual(me["me"], {"user": "lea", "name": "LEA", "email": "lea@example.com", "groups": ["friends", "qa"]})
        self.assertEqual(self.app.call("/").status, 401, "pages need the sign-in")
        r = self.app.call("/", headers=as_user("lea", []))
        self.assertEqual(r.status, 200)
        self.assertIn("<title>", r.text)
        self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])
        self.assertEqual(self.app.call("/api/messages").status, 401)

    def test_the_sign_out_link_follows_the_address(self):
        me = self.app.call("/api/me", headers={**as_user("lea", []), "Host": "notes.example.com"}).json()
        self.assertEqual(me["signOut"], "https://auth.example.com/logout")

    def test_posting_needs_the_apps_own_header_and_deleting_the_admins_group(self):
        lea, marc = as_user("lea", ["friends"]), as_user("marc", ["admins"])
        r = self.app.call("/api/messages", "POST", {**lea, "Content-Type": "application/json"}, '{"text":"hi"}')
        self.assertEqual(r.status, 403, "a request from another site is refused")
        r = self.app.call("/api/messages", "POST", {**lea, **CHANGE, "Origin": "https://evil.example"}, '{"text":"hi"}')
        self.assertEqual(r.status, 403, "a foreign Origin is refused")
        r = self.app.call("/api/messages", "POST", {**lea, **CHANGE}, '{"text":"  "}')
        self.assertEqual((r.status, r.json()["message"]), (400, "Write something first."))
        r = self.app.call("/api/messages", "POST", {**lea, **CHANGE}, "not json")
        self.assertEqual(r.status, 400)
        r = self.app.call("/api/messages", "POST", {**lea, **CHANGE}, json.dumps({"text": "x" * 70_000}))
        self.assertEqual(r.status, 413)
        item = self.app.call("/api/messages", "POST", {**lea, **CHANGE}, '{"text":"Hello <b>"}').json()["item"]
        self.assertEqual(item["by"], "LEA")
        self.assertEqual(self.app.call("/api/messages", headers=lea).json()["messages"][0]["text"], "Hello <b>")
        self.assertEqual(self.app.call(f"/api/messages/{item['id']}", "DELETE", {**lea, **CHANGE}).status, 403)
        self.assertEqual(self.app.call(f"/api/messages/{item['id']}", "DELETE", {**marc, **CHANGE}).status, 200)
        self.assertEqual(self.app.call(f"/api/messages/{item['id']}", "DELETE", {**marc, **CHANGE}).status, 404)
        r = self.app.call("/api/messages", "PUT", {**marc, **CHANGE})
        self.assertEqual((r.status, r.json()["ok"]), (405, False))
        r = self.app.call("/api/nothing", headers=marc)
        self.assertEqual((r.status, r.json()["ok"]), (404, False))

    def test_pages_only_come_from_public(self):
        lea = as_user("lea", [])
        self.assertEqual(self.app.call("/style.css", headers=lea).status, 200)
        for path in ("/nothing.html", "/..%2fpyproject.toml", "/%2e%2e/app/main.py", "/ds/..%2f..%2fcontrol-center.yml"):
            self.assertEqual(self.app.call(path, headers=lea).status, 404, path)
        first = self.app.call("/app.js", headers=lea)
        again = self.app.call("/app.js", headers={**lea, "If-None-Match": first.headers["ETag"]})
        self.assertEqual(again.status, 304, "an unchanged file is not sent twice")


class PublicApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Running(SIGNIN="none")

    @classmethod
    def tearDownClass(cls):
        cls.app.stop()

    def test_1_it_never_believes_the_sign_in_headers(self):
        forged = as_user("forged", ["admins"])
        self.assertIsNone(self.app.call("/api/me", headers=forged).json()["me"])
        self.assertEqual(self.app.call("/").status, 200, "pages open without a sign-in")
        item = self.app.call("/api/messages", "POST", {**forged, **CHANGE}, '{"text":"hi"}').json()["item"]
        self.assertEqual(item["by"], "Anonymous", "posts are anonymous, whatever the headers say")
        r = self.app.call(f"/api/messages/{item['id']}", "DELETE", {**forged, **CHANGE})
        self.assertEqual(r.status, 401, "a forged admin cannot delete")

    def test_2_anyone_reads_and_posts_within_a_limit(self):
        me = self.app.call("/api/me").json()
        self.assertEqual((me["signin"], me["signOut"]), ("none", None))
        self.assertEqual(self.app.call("/api/messages").status, 200, "reading needs no sign-in")
        r = self.app.call("/api/messages", "POST", {"Content-Type": "application/json"}, '{"text":"hi"}')
        self.assertEqual(r.status, 403, "changes still need the app's own header")
        status = 200
        for _ in range(25):
            status = self.app.call("/api/messages", "POST", CHANGE, '{"text":"spam"}').status
            if status != 200:
                break
        self.assertEqual(status, 429, "posting is capped")


class DevMode(unittest.TestCase):
    def test_it_signs_in_a_fake_user_with_the_groups_asked_for(self):
        dev = Running(DEV="1", DEV_USER="sam", DEV_GROUPS="devs,qa")
        try:
            me = dev.call("/api/me").json()["me"]
            self.assertEqual((me["user"], me["groups"]), ("sam", ["devs", "qa"]))
        finally:
            dev.stop()

    def test_with_signin_none_it_runs_as_the_public_app(self):
        dev = Running(DEV="1", SIGNIN="none")
        try:
            self.assertIsNone(dev.call("/api/me").json()["me"])
        finally:
            dev.stop()


if __name__ == "__main__":
    unittest.main()
