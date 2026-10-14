"""Reset the working database from the untouched original.

Run before every full run:  .venv/bin/python -m backend.reset_db
"""

import shutil

from backend.audit import AuditTrail
from backend.config import AUDIT_TRAIL_PATH, DB_PATH, ORIGINAL_DB


def reset_db() -> None:
    # copyfile copies contents only, so the working copy stays writable even
    # though the original is read-only.
    shutil.copyfile(ORIGINAL_DB, DB_PATH)
    AuditTrail(AUDIT_TRAIL_PATH).append({"step_type": "reset", "database": DB_PATH.name})


if __name__ == "__main__":
    reset_db()
    print(f"Reset {DB_PATH.name} from {ORIGINAL_DB.name}")
