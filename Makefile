# Define all phony targets (targets that don't represent files)
.PHONY: clean clean-build clean-venv clean-cache setup install setup-all orchestrate \
        coordinator github-sensor hackmd-sensor processor-gh processor-hackmd \
        run-all demo-coordinator demo-github demo-hackmd docker-clean docker-rebuild up down

VENV_DIR ?= .venv
PYTHON_EXECUTABLE_FOR_VENV_CREATION ?= python3.12 # Make sure this command works on your system

# Setup targets
setup: $(VENV_DIR)/.pip_ready
	@echo "Root virtual environment is ready at $(VENV_DIR)"
	@echo "To activate, run: source $(VENV_DIR)/bin/activate"

install: $(VENV_DIR)/.installed_root_requirements
	@echo "Root requirements from requirements.txt are installed in $(VENV_DIR)."
	@echo "Installing/checking koi-net package into $(VENV_DIR)..."
	. $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pip install koi-net
	@echo "koi-net installation/check complete."

# --- Helper targets for venv and root requirements ---
# Marker file indicating venv is created and base pip is ready
$(VENV_DIR)/.pip_ready:
	@echo "Creating root virtual environment in $(VENV_DIR) using $(PYTHON_EXECUTABLE_FOR_VENV_CREATION)..."
	$(PYTHON_EXECUTABLE_FOR_VENV_CREATION) -m venv $(VENV_DIR)
	@echo "Ensuring pip is installed and up-to-date in $(VENV_DIR)..."
	. $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/python -m ensurepip --upgrade --default-pip
	. $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pip install --upgrade pip
	@touch $@

# Marker file indicating requirements.txt are installed
$(VENV_DIR)/.installed_root_requirements: $(VENV_DIR)/.pip_ready requirements.txt
	@echo "Installing root requirements from requirements.txt into $(VENV_DIR)..."
	. $(VENV_DIR)/bin/activate && $(VENV_DIR)/bin/pip install -r requirements.txt
	@touch $@

# --- End of modified/added section for setup and install ---

setup-all:
	@echo "Setting up all node repositories..."
	python orchestrator.py

clean:
	@echo "Starting full cleanup..."
	@$(MAKE) clean-cache
	@$(MAKE) clean-venv
	@$(MAKE) clean-build
	@echo "Clean complete."

# Cleaning targets
clean-build:
	@echo "Removing build artifacts..."
	@find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name 'dist' -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name 'build' -exec rm -rf {} + 2>/dev/null || true
	@echo "Build artifacts removed."

clean-venv:
	@echo "Removing virtual environments..."
	@rm -rf .venv || true
	@find . -name ".venv" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Virtual environments removed."

clean-cache:
	@echo "Removing problematic files from cache directories (e.g., .DS_Store)..."
	@find . -name ".DS_Store" -type f -exec rm -f {} + 2>/dev/null || true
	@echo "Removing cache directories and files..."
	@find . -name ".koi" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name ".rid_cache" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "event_queues.json" -type f -exec rm -f {} + 2>/dev/null || true
	# @find . -name "config.yaml" -type f -exec rm -f {} + 2>/dev/null || true
	# @echo "Cache and config.yaml files removed."

# Orchestration target
orchestrator: install
	. $(VENV_DIR)/bin/activate && python simple_orchestrator.py

# Individual node runners
coordinator:
	@echo "Running Coordinator Node..."
	.venv/bin/python -m coordinator_node

github-sensor: clean-cache
	@echo "Running Github Sensor Node..."
	.venv/bin/python -m github_sensor_node

hackmd-sensor:
	@echo "Running HackMD Sensor Node..."
	rm -rf koi-net-hackmd-sensor-node/node.sensor.log
	.venv/bin/python -m hackmd_sensor_node

processor-gh:
	@echo "Running GitHub Processor Node..."
	.venv/bin/python -m processor_a_node

processor-hackmd:
	@echo "Running HackMD Processor Node..."
	rm node.proc.log >/dev/null || true
	.venv/bin/python -m hackmd_processor_node
