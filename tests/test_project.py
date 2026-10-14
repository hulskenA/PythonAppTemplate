"""What the server needs from the repository to install and start the app."""
import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Project(unittest.TestCase):
    def test_the_lock_file_is_there_and_lists_what_the_app_needs(self):
        lock = ROOT / "uv.lock"
        self.assertTrue(lock.is_file(), "uv.lock is missing: run `uv lock` and commit the file. The server installs with `uv sync --locked`, which refuses to choose versions itself.")
        locked = {p["name"] for p in tomllib.loads(lock.read_text(encoding="utf-8")).get("package", [])}
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        # The lock file also names the project itself: renaming it, or changing its version,
        # needs `uv lock` again, or the server's install step refuses the file.
        own = [(p["name"], p["version"]) for p in tomllib.loads(lock.read_text(encoding="utf-8")).get("package", []) if p.get("source") == {"virtual": "."}]
        self.assertEqual(own, [(project["name"], project["version"])], "the name or version in pyproject.toml changed since uv.lock was written: run `uv lock` and commit uv.lock")
        for dependency in project["dependencies"]:
            name = re.split(r"[\s\[<>=!~;]", dependency.strip(), maxsplit=1)[0].lower().replace("_", "-")
            self.assertIn(name, locked, f"{name} is in pyproject.toml but not in uv.lock: run `uv lock` and commit uv.lock")

    def test_the_start_command_passes_the_port_on(self):
        file = (ROOT / "control-center.yml").read_text(encoding="utf-8")
        start = re.search(r"^start:\s*(.+)$", file, flags=re.M)
        self.assertTrue(start, "control-center.yml needs a start: line")
        self.assertIn("$PORT", start.group(1), "the start command must pass $PORT to the server: the panel chooses the port")
        self.assertIn("127.0.0.1", start.group(1), "listen on 127.0.0.1 only: nginx is the one door in")


if __name__ == "__main__":
    unittest.main()
