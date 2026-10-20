import uvicorn

from app.backend.api import create_app
from app.config import load_settings

if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8000)
