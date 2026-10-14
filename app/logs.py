"""What goes where in the log. logging.json uses this.

Control Center keeps two streams per app: the normal one and the error one, which it counts and
groups as errors. Left alone, uvicorn writes its own "Started server process" lines to the error
stream, and one line per request (the health check alone is 2,880 a day). So: information goes
to the normal stream, warnings and errors to the error stream, and requests are not logged here
(nginx logs them, and the panel shows the failed ones between the app's lines).

In the app:   log = logging.getLogger("app")   then   log.info(...), log.warning(...), log.exception(...)
"""
import logging


class BelowWarning(logging.Filter):
    """Lets through what is less than a warning: the normal stream's share."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.WARNING
