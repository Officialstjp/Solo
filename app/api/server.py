"""
Module Name: app/api/server.py
Purpose   : HTTP server for Solo API.
Params    : None
History   :
    Date            Notes
    2025-06-08      Init

"""
import uvicorn
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config import get_config
from app.utils.logger import get_logger
from app.api.factory import create_app

logger = get_logger(name="API_Server", json_format=False)

def start_server():
    config = get_config()
    app = create_app()
    logger.info(f"Starting API server on port {config.api_port}")
    uvicorn.run(app, host="0.0.0.0", port=config.api_port)

if __name__ == "__main__":
    start_server()
