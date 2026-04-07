import structlog
from koi_net.core import FullNode

from . import handlers
from .config import GithubSensorConfig
from .ingestion import GithubIngestionService

log = structlog.stdlib.get_logger()


class GithubSensorNode(FullNode):
    config_schema = GithubSensorConfig
    suppress_peer_node_rebroadcast_handler = (
        handlers.SuppressPeerNodeRebroadcastHandler
    )
    github_bundle_handler = handlers.GithubBundleHandler
    github_logging_handler = handlers.GithubLoggingHandler
    ingestion_service: GithubIngestionService = GithubIngestionService

if __name__ == "__main__":
    GithubSensorNode().run()
