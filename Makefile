# ==============================================================================
# Makefile for KOI-net GitHub Sensor Node
# ==============================================================================

# --- Configuration ---
NODE_NAME       := github_sensor
MODULE_NAME     := koi_net_github_sensor_node
PORT            := 8007
# --- End Configuration ---

# --- Variables ---
ROOT_DIR        := ..
LOGS_DIR        := $(ROOT_DIR)/logs
LOG_FILE        := $(LOGS_DIR)/$(NODE_NAME).log
ENV_FILE        := $(ROOT_DIR)/.env
PYTHON_CMD      := uv run --env-file $(ENV_FILE) python -m $(MODULE_NAME)

.PHONY: all install setup-venv build-shared start stop status dev logs clean health-check

all: install

install: setup-venv build-shared
	@echo "Installing $(NODE_NAME) node..."
	@uv pip install -e ".[dev]"

setup-venv:
	@if [ ! -d ".venv" ]; then \
		echo "Setting up virtual environment for $(NODE_NAME)..."; \
		uv venv --python=python3.12; \
	else \
		echo "Virtual environment for $(NODE_NAME) already exists."; \
	fi

build-shared:
	@echo "Building shared koi-net packages..."
	@cd $(ROOT_DIR)/koi-net && uv build
	@cd $(ROOT_DIR)/koi-net-shared && uv build

start:
	@echo "Starting $(NODE_NAME) node in background..."
	@rm -f log.ndjson
	@$(PYTHON_CMD)
	@echo "$(NODE_NAME) started. Log file: $(LOG_FILE)"

stop:
	@echo "Stopping $(NODE_NAME) node..."
	@pid=$$(lsof -ti :$(PORT) 2>/dev/null); \
	if [ -n "$$pid" ]; then \
		echo "  Killing process $$pid on port $(PORT)"; \
		kill $$pid 2>/dev/null || true; \
	else \
		echo "  No process found on port $(PORT)."; \
	fi

status:
	@echo "Checking status for $(NODE_NAME) node:"
	@pid=$$(lsof -ti :$(PORT) 2>/dev/null); \
	if [ -n "$$pid" ]; then \
		echo "  $(NODE_NAME): RUNNING (PID: $$pid, Port: $(PORT))"; \
	else \
		echo "  $(NODE_NAME): STOPPED"; \
	fi

dev:
	@echo "Running $(NODE_NAME) node in development mode (foreground)..."
	@$(PYTHON_CMD)

logs:
	@echo "Following logs for $(NODE_NAME) (Ctrl+C to stop)..."
	@tail -f $(LOG_FILE)

clean: stop
	@echo "Cleaning up $(NODE_NAME) node artifacts..."
	@find . -type d -name "*[cC][aA][cC][hH][eE]*" -exec rm -rf {} + 2>/dev/null || true
	@rm -f event_queues.json 2>/dev/null || true
	@rm -rf .venv 2>/dev/null || true
	@echo "Cleanup complete."

health-check:
	@echo "Checking $(NODE_NAME) node health..."
	@curl -s -f http://127.0.0.1:$(PORT)/koi-net/health >/dev/null && echo "  $(NODE_NAME): HEALTHY" || echo "  $(NODE_NAME): UNHEALTHY or STOPPED"
