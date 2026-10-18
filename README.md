# My app

Started from the **Python app template**: a small Python web app (Starlette, served by uvicorn,
installed by uv), in the house style, made to be created and deployed from Control Center.

What it already does:

- **The sign-in.** Every page and API call knows who is signed in (account, name, email, groups),
  and `require_group(request, "admins")` limits a route to a group. A **Sign out** link sits in
  the header.
- **The charter.** Tokens, fonts, cards, fields, buttons and the duck: pages look like the panel.
- **A small API** with the usual guards: JSON bodies with a size limit, changes accepted only from
  the app's own pages, clear error messages, security headers on every answer.
- **What the panel expects:** listens on `127.0.0.1` and the port the panel gives it, answers
  `/health`, writes its log to the console (errors apart from the rest), stops cleanly when PM2
  restarts it.
- **Tests** and a **local mode** (`uv run dev.py`) with a fake signed-in user.
- **A guide** (`docs/`): the app's page on the documentation site, updated by each deploy.

The home page is an example (a message board kept in memory): replace it.

## What you need on your PC

[uv](https://docs.astral.sh/uv/getting-started/installation/), and nothing else: it downloads
the right Python (the one in `.python-version`) and the packages by itself.

## Starting a new app from the template

1. On GitHub, open the template repository and press **Use this template**, then
   **Create a new repository**. Give it the app's name, private.
2. Add the new repository to the server's GitHub token (the same token the panel uses), so the
   server can read it.
3. Clone it on your PC and change the name in four places:
   - `pyproject.toml`: `name`
   - `control-center.yml`: `name`, `address`, `access` and `group`, and `APP_NAME`
   - `public/index.html`: the `<title>` (the page fills in the rest from `APP_NAME`)
   - `docs/index.md`: its `# title`, the name people see on the documentation site
4. Run **`uv lock`**: the lock file carries the project's name, so it has to be written again
   after the rename. Then `uv run python -m unittest discover -s tests` to check.
5. Commit (with `uv.lock`) and push.
6. In the panel, **Add an app**, type the repository: the form fills itself from
   `control-center.yml`. It starts on the construction page; **Launch** it from its page when
   it is ready.

## Working on it

```bash
uv run dev.py                                   # http://127.0.0.1:3001, signed in as "dev" in the admins group; restarts on save
uv run python -m unittest discover -s tests     # the tests in tests/
```

The first `uv run` creates `.venv/` with Python and the packages. Another fake account:
`DEV_USER=lea DEV_GROUPS=friends,qa uv run dev.py` (in PowerShell:
`$env:DEV_USER="lea"; $env:DEV_GROUPS="friends,qa"; uv run dev.py`).

On Windows, if `uv` answers "An Application Control policy has blocked this file", Windows is
refusing the Python that uv downloads (it is not signed). Use Python from python.org instead,
once (checked on 13 Oct 2026):

```powershell
winget install Python.Python.3.13          # then open a new PowerShell
Remove-Item -Recurse -Force .venv
[Environment]::SetEnvironmentVariable("UV_PYTHON_PREFERENCE", "only-system", "User")
$env:UV_PYTHON_PREFERENCE = "only-system"
uv sync
```

Do not switch Smart App Control off for this: Windows cannot switch it back on.

Then push, and press **Deploy** on the app's page in the panel.

## The lock file

`uv.lock` lists the exact version of every package. The server installs from it alone
(`uv sync --locked`) and refuses to deploy when it is missing or out of date, so that what runs
on the server is what ran on your PC. It is written for you by:

- `uv add <name>` and `uv remove <name>`: a package more or less;
- `uv lock`: after changing `pyproject.toml` by hand (its name and version included);
- `uv lock --upgrade`: newer versions of everything, when you choose to.

Commit `pyproject.toml` and `uv.lock` together, every time. The tests say when they disagree.

## Where things go

| Path | What |
|---|---|
| `app/routes.py` | The app's API: add routes here. Each returns a value (sent as JSON) or raises `HttpError` |
| `app/auth.py` | `who`, `require_user`, `require_group`: who is signed in |
| `app/config.py` | Everything read from the environment |
| `app/http.py` | Answers, JSON bodies, the same-origin check, static files, security headers |
| `app/main.py` | The server itself: `/health`, the API, the pages, what to do at start and stop |
| `app/logs.py`, `logging.json` | What goes to the normal log and what to the error log |
| `public/` | The pages: `index.html`, `app.js`, `common.js` (`api()`, `toast()`, `esc()`), `style.css` |
| `public/ds/` | The charter: `tokens.css` and `bundle.css`. Update both from the panel when the charter changes |
| `docs/` | The app's guide, shown on the documentation site: see below |
| `tests/` | Tests, worth running before each push |
| `dev.py` | Local mode |
| `pyproject.toml`, `uv.lock`, `.python-version` | The packages, their exact versions, and the Python to run them with |
| `control-center.yml` | How the panel creates and deploys the app |

## How the server runs it

`control-center.yml` gives the panel two commands:

```yaml
install: uv sync --locked --no-dev
start: .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $PORT --log-config logging.json
```

- **Install** runs in each new build's folder and creates its own `.venv/`, so a rollback also
  brings back the packages of that build.
- **Start** runs uvicorn from that `.venv/`. The panel picks the port and puts it in place of
  `$PORT`: keep `$PORT` and `127.0.0.1` in the command if you change it (the tests check). One
  process is enough for most apps and takes about 60 MB; `--workers 2` doubles that.
- **The log.** In the code, `log = logging.getLogger("app")`, then `log.info(...)`,
  `log.warning(...)`, `log.exception(...)`. Warnings and errors go to the error log, which the
  panel counts and groups; the rest goes to the normal log. Requests are not logged by the app:
  nginx logs them, and the panel shows the failed ones between the app's lines.

## The guide

`docs/` is what people read about the app on the documentation site, under **Apps**. There is
nothing to set up: the site reads the folder from the app's live build, so each **Deploy**
updates the guide, and it is shown to the people who can open the app and to nobody else.

- `docs/index.md` is the first page. Its `# title` is the app's name in the list of apps.
- Each other `.md` file is another page. Pictures go in the folder too: `![The list](img/list.png)`.
- Write links as on GitHub, relative to the file: `[sharing](sharing.md)`.
- Markdown only: HTML typed in a page is shown as text.
- To order the pages, or to shorten a title in the menu, start a file with settings between two
  `---` lines: `title`, `nav`, `order`, `summary`, and `access` (a group, to limit one page).

The page in `docs/` is an example: replace it. The tests check that each page has a title and
that every link and picture of the guide leads to a file. The documentation site explains the
rest, under Building an app, "Document your app".

## Settings and secrets

Plain settings go in `control-center.yml` under `env:` (they are on GitHub), or on the app's page
under **Edit settings**. API keys, passwords and tokens go under **Secrets** on the app's page:
they stay on the server and reach the app as environment variables. Read both in
`app/config.py` with `os.environ.get(...)`, with a default for `uv run dev.py`.

| Variable | Default | Meaning |
|---|---|---|
| `APP_NAME` | `My app` | Shown in the header and the title |
| `SIGNIN` | `required` | `required` behind the sign-in; `none` for a public app |
| `SIGNIN_URL` | `https://auth.<the app's domain>` | The sign-in's address, for **Sign out** |
| `DATA_DIR` | `data/` in the project | The app's own folder for files and SQLite (see A database) |
| `DATABASE_URL` | empty | `database: postgres` only: the app's PostgreSQL database |
| `PORT` | `3001` locally | On the server the panel sets it and the start command passes it to uvicorn |

**Public apps:** with `access: public`, set `SIGNIN: none`. Change both together if you change the
access later from the panel: a public app left on `SIGNIN: required` answers every page with a 401.
With `SIGNIN: none`:

- Nobody is signed in: `who(request)` is `None`, there is no **Sign out**, and the sign-in's
  headers are never believed, since without the sign-in in front anyone could send them.
- `require_user` and `require_group` refuse everyone (401). Keep them on what only an account may
  do; write the routes anyone may use without them (the example board lets anyone read and post,
  as *Anonymous*).
- Cap what anyone can do with `rate_limit(limit, seconds)` from `app/http.py` (the board: 20 posts
  a minute). Changes still need the app's own pages (`api()`), as behind the sign-in.
- Try it locally with `SIGNIN=none uv run dev.py` (in PowerShell: `$env:SIGNIN="none"; uv run dev.py`).

## Using FastAPI, or another framework

The template uses Starlette, the small framework FastAPI itself is built on, to keep the list of
packages short. To write routes the FastAPI way, `uv add fastapi`, create the app in
`app/main.py` with `FastAPI(...)` instead of `Starlette(...)`, and keep the rest: `who(request)`,
`require_group`, `read_json`, the same-origin check and the security headers work on FastAPI's
requests too, since they are Starlette's (this has not been tried in the template itself). For Flask or Django, keep `control-center.yml`,
`docs/`, `public/` and the ideas of `app/auth.py`, add `gunicorn`, and change the start command
(`.venv/bin/gunicorn -b 127.0.0.1:$PORT ...`).

## A database

Set `database:` in `control-center.yml` (or on the app's page, Control Center 0.20):

| Value | The app gets |
|---|---|
| `none` (default) | Nothing: no data kept across deploys |
| `sqlite` | `DATA_DIR`, its own folder on the server, kept across deploys and rollbacks. Put SQLite files there, with Python's own `sqlite3` module (no package to add) |
| `postgres` | `DATA_DIR`, and `DATABASE_URL`, its own database on the server's PostgreSQL. Add a PostgreSQL client package (for example `uv add psycopg`) |

`app/config.py` reads both. Locally, `DATA_DIR` is `data/` in the project (made at start, not in git)
and `DATABASE_URL` is empty unless you set it. The panel copies each database every night (the
last 7 kept). Choose before the first deploy: switching between `sqlite` and `postgres` later
is refused, since the panel does not convert data. A staging copy starts with its own empty data.

## Rules worth keeping

- Escape what you put in a page (`esc()` in `public/common.js`); never build HTML from raw input.
- Calls that change something go through `api()`, which sends the header the server checks.
- Data in memory is gone at each deploy and restart. For data to keep, use `DATA_DIR` or
  `DATABASE_URL` (see A database), never the app's folder (each deploy is a new folder).
- Keep `/health` cheap: the panel calls it every 30 seconds.
- A route that waits (a slow API, a big file) should be an `async def` that awaits, or it holds
  up everyone else: the app is one process.
- Adding a package: `uv add <name>`, then commit `pyproject.toml` and `uv.lock`.

## Tests and deploys on GitHub

`.github/workflows/ci.yml` runs the tests on every push and pull request. It can also deploy
once they pass (Control Center 0.19), and does nothing of the kind until you set it up:

1. On the app's page in the panel, **Deploy from CI** > **Make a deploy link**. Copy the token.
2. In the repository on GitHub, Settings > Secrets and variables > Actions: the variable
   `CC_DEPLOY_URL` (the link shown in the panel) and the secret `CC_DEPLOY_TOKEN` (the token).
3. Push to `main`: when the tests pass, the panel deploys that commit, with its usual check and
   automatic rollback. A commit is deployed only while it is still the latest on `main`.

For a staging copy, do the same on the copy's page with `CC_STAGING_URL` and `CC_STAGING_TOKEN`:
pushes to other branches are sent, and the copy deploys only the branch it follows. If the app
deploys from another branch than `main`, change `refs/heads/main` in the workflow too.
