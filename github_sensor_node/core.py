import logging
from koi_net import NodeInterface
# Import default handlers if needed, or custom ones from .handlers
from koi_net.processor.default_handlers import (
    basic_rid_handler,
    basic_manifest_handler,
    edge_negotiation_handler,
    basic_network_output_filter
)

from .config import GitHubSensorNodeConfig

logger = logging.getLogger(__name__)


config_file_path = "config.yaml"
try:
    loaded_config = GitHubSensorNodeConfig.load_from_yaml(config_file_path)
    logger.info(f"Successfully loaded configuration from {config_file_path}")
except FileNotFoundError:
    logger.warning(f"Configuration file {config_file_path} not found. Using default configuration.")
    loaded_config = GitHubSensorNodeConfig() # Use defaults if no file
except Exception as e:
    logger.error(f"Error loading configuration from {config_file_path}: {e}. Using default configuration.")
    loaded_config = GitHubSensorNodeConfig()


node = NodeInterface(
    config=loaded_config,
    use_kobj_processor_thread=True, # Recommended for sensors that might do I/O in handlers
    handlers=[
        basic_rid_handler,
        basic_manifest_handler,
        edge_negotiation_handler,
        basic_network_output_filter,
    ]
)

# Import local handlers to register them with the node.processor
from . import handlers as sensor_specific_handlers # noqa: F401 ensure handlers are loaded

logger.info(f"GitHub Sensor Node Interface initialized with name: {node.config.koi_net.node_name}")
logger.info(f"Monitored repositories: {node.config.github.monitored_repositories}")

# # Ensure essential environment variables are present for core functionality
# if not node.config.env.github_token:
#     logger.warning("GITHUB_TOKEN environment variable is not set. API calls to GitHub may fail or be severely rate-limited.")
# if not node.config.env.github_webhook_secret:
#     logger.warning("GITHUB_WEBHOOK_SECRET environment variable is not set. Webhook verification will be skipped (INSECURE).")
