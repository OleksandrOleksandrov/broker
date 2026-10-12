"""Local development entry point.

The real application lives in ``api.main``. This shim exists so uvicorn can be
started from the ``backend/`` directory as well as from ``backend/api/``:

    cd backend     && uvicorn main:app --reload
    cd backend/api && uvicorn main:app --reload

Without it, the first form fails with "No module named 'main'". Note that a
failed worker start is easy to miss: with --reload uvicorn keeps the reloader
process alive holding a closed listening socket, so requests fail with
ERR_CONNECTION_TIMED_OUT rather than a visible error.
"""

from api.main import app

__all__ = ["app"]
