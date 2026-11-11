from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend directory to sys.path
if getattr(sys, "frozen", False):
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    bundle_dir = Path(__file__).resolve().parent

if str(bundle_dir) not in sys.path:
    sys.path.insert(0, str(bundle_dir))

from app.main import app

def run_server(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    # Set desktop mode flag
    os.environ["PRIVORA_DESKTOP"] = "1"
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    run_server(host=host, port=port)
