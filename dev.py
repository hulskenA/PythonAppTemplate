"""Local mode: `uv run dev.py`.

http://127.0.0.1:3001, signed in as "dev" in the admins group, restarting on each save.
Another fake account: DEV_USER=lea DEV_GROUPS=friends,qa uv run dev.py
A public app:         SIGNIN=none uv run dev.py
"""
import os

import uvicorn

if __name__ == "__main__":
    os.environ["DEV"] = "1"
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT") or 3001), reload=True, reload_dirs=["app"], log_config="logging.json")
