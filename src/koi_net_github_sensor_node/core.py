import structlog
from koi_net.core import FullNode

from . import handlers
from .config import GithubSensorConfig
from .ingestion import GithubIngestionService

log = structlog.stdlib.get_logger()


class GithubSensorNode(FullNode):
    config_schema = GithubSensorConfig
    # Place prepend handlers before defaults, then append handlers
    knowledge_handlers = (
        handlers.PREPEND_HANDLERS
        + FullNode.knowledge_handlers
        + handlers.APPEND_HANDLERS
    )
    ingestion_service: GithubIngestionService = GithubIngestionService

if __name__ == "__main__":
    GithubSensorNode().run()
