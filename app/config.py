"""Everything the app reads from its environment, in one place.

On the server, Control Center sets the variables of control-center.yml's `env:`, plus the secrets
added on the app's page. Locally, `uv run dev.py` fills in what is missing.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# `uv run dev.py`: a fake signed-in user, no sign-in in front (none with SIGNIN=none). Set by dev.py
# alone, under a name nothing else uses, and never where PM2 runs the app (pm_id), as on the server.
DEV = os.environ.get("APP_DEV_FAKE_SIGNIN") == "1" and "pm_id" not in os.environ

APP_NAME = os.environ.get("APP_NAME") or "My app"

# Where the app keeps files and SQLite databases. On the server (database: sqlite or postgres in
# control-center.yml) the panel sets it to the app's own folder, kept across deploys and
# rollbacks; locally it is data/ in the project (not in git). Never write into the code folder:
# each deploy is a new one.
DATA_DIR = Path(os.environ.get("DATA_DIR") or ROOT / "data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# database: postgres only: postgresql://<role>:<password>@127.0.0.1:5432/<db>. Empty otherwise.
DATABASE_URL = os.environ.get("DATABASE_URL") or ""

# How the app knows who is signed in.
#   required  the sign-in is in front (access: account, group or admins). The account comes
#             from the headers nginx sets after the sign-in; a request without them is refused.
#   none      a public app (access: public). Nobody is signed in, and those headers are never
#             believed, since anyone could send them.
# Change it together with the app's access in the panel.
SIGNIN = "none" if (os.environ.get("SIGNIN") or "required").lower() == "none" else "required"

# The sign-in's address, for the "Sign out" link. Default: auth.<the app's domain>.
SIGNIN_URL = os.environ.get("SIGNIN_URL") or ""

# The fake account of `uv run dev.py`: DEV_USER=lea DEV_GROUPS=friends,qa uv run dev.py
DEV_USER = os.environ.get("DEV_USER") or "dev"
DEV_GROUPS = [g.strip() for g in (os.environ.get("DEV_GROUPS") or "admins").split(",") if g.strip()]
