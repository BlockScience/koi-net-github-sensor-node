import uvicorn
import logging
from .core import node

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if not node.config.server or not node.config.server.host or node.config.server.port is None:
        logger.critical("Server configuration (host/port) is missing in the loaded config. Cannot start.")
        exit(1)

    logger.info(f"Starting HackMD sensor node server on {node.config.server.host}:{node.config.server.port}")
    uvicorn.run(
        "github_sensor_node.server:app",
        host=node.config.server.host,
        port=node.config.server.port,
        log_config=None,
        reload=False
    )
