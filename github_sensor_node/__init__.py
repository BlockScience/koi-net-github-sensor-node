import logging
from rich.logging import RichHandler
import sys

# Configure root logger for the application
# This will ensure that all loggers created via logging.getLogger(__name__)
# will inherit this basic configuration if not configured otherwise.

# Determine if running in a test environment (e.g., pytest)
# to avoid duplicate handlers if conftest.py also configures logging.
IS_TESTING = "pytest" in sys.modules

if not IS_TESTING:
    logger = logging.getLogger() # Get the root logger
    logger.setLevel(logging.DEBUG) # Default level for the application

    # Clear existing handlers from the root logger to avoid duplicates if script is re-run
    if logger.hasHandlers():
        logger.handlers.clear()

    # Rich Handler for console output
    rich_handler = RichHandler(rich_tracebacks=True, show_path=False)
    rich_handler.setLevel(logging.DEBUG) # Console logs INFO and above
    rich_handler.setFormatter(logging.Formatter(
        "%(name)s - %(message)s", # Simplified format for Rich
        datefmt="[%X]"
    ))
    logger.addHandler(rich_handler)

    # File Handler for persistent logs
    try:
        file_handler = logging.FileHandler("github-sensor-node.log", mode='a')
        file_handler.setLevel(logging.DEBUG) # File logs DEBUG and above
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(file_handler)
    except PermissionError:
        # Fallback if file can't be written (e.g. in some container environments)
        logging.error("Permission denied to write to github-sensor-node.log. File logging disabled.")

    logging.info("Logging configured for GitHub Sensor Node.")
else:
    # In test environment, assume pytest's logging capture or conftest.py handles it.
    logging.info("Detected testing environment. Skipping default logging setup in __init__.")

# Example: Quieting overly verbose libraries if needed
# logging.getLogger("httpx").setLevel(logging.WARNING)
