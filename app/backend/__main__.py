import os

import uvicorn

from app.backend.api import create_app
from app.config import load_settings

if __name__ == "__main__":
    settings = load_settings()
    # 127.0.0.1 for bare-metal runs; containers set BACKEND_HOST=0.0.0.0
    uvicorn.run(create_app(settings), host=os.environ.get("BACKEND_HOST", "127.0.0.1"), port=8000)
