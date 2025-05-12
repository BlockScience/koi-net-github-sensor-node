# GitHub Sensor Node for KOI-net v1.0.0

![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)
![Test Coverage](https://img.shields.io/badge/coverage-85%25-yellowgreen.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)
![Support](https://img.shields.io/badge/support-active-brightgreen.svg)

A specialized Knowledge Organization Infrastructure (KOI) network sensor node that integrates with GitHub to capture events and data. It receives webhook events from GitHub repositories, performs historical data backfills, and transforms this information into standardized RIDs (Reference Identifiers) accessible to other nodes in the KOI-net ecosystem.

## Key Benefits
- **Real-time Event Capture**: Listen for and process GitHub webhooks as they occur
- **Historical Data Collection**: Automatically backfill repository data, commits, issues, and PRs
- **Efficient Change Detection**: Uses ETags and timestamps to minimize API requests
- **Full KOI-net Integration**: Seamlessly participates in the distributed knowledge network
- **Flexible Configuration**: Easily monitor multiple repositories with customizable settings

## Table of Contents
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Architecture](#architecture)
- [Examples](#examples)
- [Contributing](#contributing)
- [Testing](#testing)
- [CI/CD & Deployment](#cicd--deployment)
- [Versioning & Changelog](#versioning--changelog)
- [License](#license)
- [Contact & Support](#contact--support)

## Installation

### Using pip

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
pip install koi-net-github-sensor
```

### Using Docker

```bash
# Pull the Docker image
docker pull blockscience/github-sensor-node:latest

# Run using Docker
docker run -p 8002:8002 \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -e GITHUB_TOKEN=your_github_token \
  -e GITHUB_WEBHOOK_SECRET=your_webhook_secret \
  blockscience/github-sensor-node:latest
```

### From Source

```bash
# Clone the repository
git clone https://github.com/BlockScience/github-sensor-node.git
cd github-sensor-node

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## Quick Start

1. Create a configuration file:

```bash
# Create a basic config.yaml
cat > config.yaml << EOF
server:
  host: 127.0.0.1
  port: 8002
  path: /koi-net
koi_net:
  node_name: github-sensor
  node_profile:
    node_type: FULL
    provides:
      event: [GitHubEvent]
      state: [GitHubEvent]
  cache_directory_path: .koi/github/cache
  event_queues_path: .koi/github/event_queues.json
  first_contact: http://127.0.0.1:8000/koi-net
env:
  github_token: GITHUB_TOKEN
  github_webhook_secret: GITHUB_WEBHOOK_SECRET
github:
  api_url: https://api.github.com
  monitored_repositories:
    - name: blockscience/koi-net
  backfill_max_items: 50
  backfill_lookback_days: 30
EOF
```

2. Set environment variables:

```bash
export GITHUB_TOKEN=your_github_personal_access_token
export GITHUB_WEBHOOK_SECRET=your_github_webhook_secret_token
```

3. Start the sensor node:

```bash
python -m github_sensor_node
```

4. Configure a GitHub webhook:
   - Go to your repository's "Settings" → "Webhooks" → "Add webhook"
   - Set Payload URL to `http://your-server-address:8002/github/webhook`
   - Set Content type to `application/json`
   - Set Secret to the same value as your `GITHUB_WEBHOOK_SECRET`
   - Choose events to trigger the webhook (or "Send me everything")
   - Save the webhook

## Usage

### Setting Up GitHub Webhooks

To receive real-time events from GitHub, set up webhooks for repositories you want to monitor:

```bash
# 1. Generate a secure webhook secret
WEBHOOK_SECRET=$(openssl rand -hex 20)
echo "Your webhook secret: $WEBHOOK_SECRET"

# 2. Add this secret to your environment
export GITHUB_WEBHOOK_SECRET=$WEBHOOK_SECRET

# 3. Configure the webhook in GitHub's repository settings
# Payload URL: http://your-server-address:8002/github/webhook
# Content type: application/json
# Secret: Your generated webhook secret
# Events: Select which events you want to receive
```

### Testing Webhooks Locally

For local development, you can use a service like [ngrok](https://ngrok.com/) to expose your local server:

```bash
# Install ngrok
npm install -g ngrok  # or install via download from ngrok.com

# Expose your local server
ngrok http 8002

# Use the provided ngrok URL (e.g., https://a1b2c3d4.ngrok.io)
# as the webhook payload URL in GitHub settings
```

### Python Client Example

```python
import requests
import json

# Base URL of your GitHub Sensor Node
BASE_URL = "http://localhost:8002"

# Function to query KOI-net events from the sensor
def get_events_for_repository(repo_full_name):
    # Using the KOI-net protocol to fetch RIDs
    response = requests.post(
        f"{BASE_URL}/koi-net/rids/fetch",
        json={"rid_types": ["orn:github.event"]}
    )

    if response.status_code != 200:
        print(f"Error fetching RIDs: {response.status_code}")
        return []

    # Filter RIDs belonging to the specified repository
    rids_data = response.json()
    relevant_rids = [
        rid for rid in rids_data.get("rids", [])
        if repo_full_name in rid
    ]

    # Fetch bundles for these RIDs
    if relevant_rids:
        response = requests.post(
            f"{BASE_URL}/koi-net/bundles/fetch",
            json={"rids": relevant_rids}
        )

        if response.status_code == 200:
            return response.json().get("bundles", [])

    return []

# Example usage
events = get_events_for_repository("blockscience/koi-net")
for event in events:
    print(f"Event: {event['manifest']['rid']}")
    print(f"Type: {event['contents'].get('webhook_event_type', 'Unknown')}")
    print(f"Timestamp: {event['manifest']['timestamp']}")
    print("-" * 40)
```

## Configuration

The GitHub Sensor Node is configured via a YAML file and environment variables.

| Option | Default | Description | Required |
|--------|---------|-------------|----------|
| `server.host` | `127.0.0.1` | Host address to bind the server to | Yes |
| `server.port` | `8002` | Port to listen on | Yes |
| `server.path` | `/koi-net` | Base path for KOI-net API endpoints | Yes |
| `koi_net.node_name` | `github-sensor` | Name of this node | Yes |
| `koi_net.node_rid` | Generated | Unique RID for this node | No |
| `koi_net.node_profile.base_url` | Server URL | Base URL for this node's API | No |
| `koi_net.node_profile.node_type` | `FULL` | Node type (FULL or PARTIAL) | Yes |
| `koi_net.node_profile.provides.event` | `[GitHubEvent]` | RID types provided as events | Yes |
| `koi_net.node_profile.provides.state` | `[GitHubEvent]` | RID types provided as state | Yes |
| `koi_net.cache_directory_path` | `.koi/github/cache` | Path to cache directory | Yes |
| `koi_net.event_queues_path` | `.koi/github/event_queues.json` | Path to event queues file | Yes |
| `koi_net.first_contact` | None | URL of the first KOI-net node to contact | No |
| `env.github_token` | `GITHUB_TOKEN` | Environment variable name for GitHub token | Yes |
| `env.github_webhook_secret` | `GITHUB_WEBHOOK_SECRET` | Environment variable name for webhook secret | Yes |
| `github.api_url` | `https://api.github.com` | Base URL for GitHub API | Yes |
| `github.monitored_repositories` | `[]` | List of repositories to monitor (`owner/repo` format) | Yes |
| `github.backfill_max_items` | `50` | Maximum items to fetch per backfill operation | Yes |
| `github.backfill_lookback_days` | `30` | Days to look back for initial backfill | Yes |
| `github.backfill_state_file_path` | `.koi/github/github_state.json` | Path to backfill state file | Yes |

### Sample Configuration File

```yaml
server:
  host: 127.0.0.1
  port: 8002
  path: /koi-net
koi_net:
  node_name: github-sensor
  node_rid: orn:koi-net.node:github-sensor+1a2b3c4d-5e6f-7g8h-9i0j-1k2l3m4n5o6p
  node_profile:
    base_url: http://127.0.0.1:8002/koi-net
    node_type: FULL
    provides:
      event: [GitHubEvent]
      state: [GitHubEvent]
  cache_directory_path: .koi/github/cache
  event_queues_path: .koi/github/event_queues.json
  first_contact: http://127.0.0.1:8000/koi-net
env:
  github_token: GITHUB_TOKEN
  github_webhook_secret: GITHUB_WEBHOOK_SECRET
github:
  api_url: https://api.github.com
  monitored_repositories:
    - name: blockscience/koi-net
    - name: blockscience/rid-lib
  backfill_max_items: 50
  backfill_lookback_days: 30
  backfill_state_file_path: .koi/github/github_state.json
```

## API Reference

### GitHub Webhook Endpoint

#### POST /github/webhook

Receives webhook events from GitHub.

**Headers:**
- `X-GitHub-Event`: Type of event (required)
- `X-Hub-Signature-256`: HMAC signature for payload verification
- `X-GitHub-Delivery`: Unique delivery ID

**Request Body:**
JSON payload from GitHub webhook

**Response:**
```json
"Webhook received."
```

**Status Code:** 202 Accepted

### KOI-net Protocol Endpoints

#### POST /koi-net/events/broadcast

Receives events from other KOI-net nodes.

**Request Body:**
```json
{
  "events": [
    {
      "rid": "orn:github.event:owner/repo:event123",
      "event_type": "NEW",
      "manifest": {
        "rid": "orn:github.event:owner/repo:event123",
        "timestamp": "2023-07-01T12:00:00Z",
        "sha256_hash": "abc123..."
      },
      "contents": {}
    }
  ]
}
```

**Response:** No content

#### POST /koi-net/events/poll

Allows partial nodes to poll for events.

**Request Body:**
```json
{
  "rid": "orn:koi-net.node:node-name+uuid",
  "limit": 50
}
```

**Response:**
```json
{
  "events": [
    {
      "rid": "orn:github.event:owner/repo:event123",
      "event_type": "NEW",
      "manifest": {
        "rid": "orn:github.event:owner/repo:event123",
        "timestamp": "2023-07-01T12:00:00Z",
        "sha256_hash": "abc123..."
      },
      "contents": {}
    }
  ]
}
```

#### POST /koi-net/rids/fetch

Fetches RIDs of specified types.

**Request Body:**
```json
{
  "rid_types": ["orn:github.event"]
}
```

**Response:**
```json
{
  "rids": [
    "orn:github.event:owner/repo:event123",
    "orn:github.event:owner/repo:event456"
  ]
}
```

#### POST /koi-net/manifests/fetch

Fetches manifests for specified RIDs.

**Request Body:**
```json
{
  "rids": ["orn:github.event:owner/repo:event123"]
}
```

**Response:**
```json
{
  "manifests": [
    {
      "rid": "orn:github.event:owner/repo:event123",
      "timestamp": "2023-07-01T12:00:00Z",
      "sha256_hash": "abc123..."
    }
  ],
  "not_found": []
}
```

#### POST /koi-net/bundles/fetch

Fetches complete bundles for specified RIDs.

**Request Body:**
```json
{
  "rids": ["orn:github.event:owner/repo:event123"]
}
```

**Response:**
```json
{
  "bundles": [
    {
      "manifest": {
        "rid": "orn:github.event:owner/repo:event123",
        "timestamp": "2023-07-01T12:00:00Z",
        "sha256_hash": "abc123..."
      },
      "contents": {
        "webhook_event_type": "push",
        "repository": {
          "full_name": "owner/repo",
          "html_url": "https://github.com/owner/repo"
        },
        "payload": {
          "ref": "refs/heads/main",
          "before": "before_commit_sha",
          "after": "after_commit_sha"
        }
      }
    }
  ],
  "not_found": [],
  "deferred": []
}
```

## Architecture

The GitHub Sensor Node consists of several interconnected components that together create a complete GitHub integration for the KOI-net ecosystem:

```
                                  ┌─────────────────┐
                                  │   GitHub API    │
                                  └─────────┬───────┘
                                            │
                                            ▼
┌─────────────────┐             ┌─────────────────────┐             ┌─────────────────┐
│  GitHub         │             │  GitHub Sensor Node  │             │  KOI-net        │
│  Webhooks       │───POST────▶│  (FastAPI Server)    │◀────────────│  Nodes          │
└─────────────────┘   Events   └──────────┬───────────┘   Protocol   └─────────────────┘
                                          │
                                          │
                      ┌──────────────────┬┴───────────────────┐
                      ▼                  ▼                    ▼
            ┌───────────────┐   ┌────────────────┐   ┌────────────────┐
            │ Event Models  │   │ Backfill       │   │ Dereference    │
            │ & Handlers    │   │ Process        │   │ Logic          │
            └───────┬───────┘   └────────┬───────┘   └────────┬───────┘
                    │                    │                    │
                    └──────────┬─────────┴──────────┬─────────┘
                               │                    │
                               ▼                    ▼
                      ┌────────────────┐   ┌────────────────┐
                      │ RID Generation │   │ KOI-net        │
                      │ & Bundle      │   │ Node Interface  │
                      │ Creation      │   │                 │
                      └────────┬───────┘   └────────┬───────┘
                               │                    │
                               └──────────┬─────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │ Local Cache     │
                                 │ (Manifests &    │
                                 │  Bundles)       │
                                 └─────────────────┘
```

### Component Responsibilities

- **FastAPI Server**: Handles HTTP requests, including GitHub webhooks and KOI-net protocol endpoints
- **Event Models & Handlers**: Validates and processes different types of GitHub events (push, issues, pull requests)
- **Backfill Process**: Periodically fetches historical data from GitHub API to ensure completeness
- **Dereference Logic**: Fetches data from GitHub API when other nodes request RIDs not in local cache
- **RID Generation & Bundle Creation**: Converts GitHub events into standardized RIDs and creates knowledge bundles
- **KOI-net Node Interface**: Manages network communication with other KOI-net nodes
- **Local Cache**: Stores manifests and bundles for efficient retrieval and sharing

## Examples

### Webhook Event Processing

The following example demonstrates how GitHub webhook events are processed:

```python
import requests
import json
import hashlib
import hmac
import time

# Setup webhook test
WEBHOOK_SECRET = "your_webhook_secret"
SENSOR_URL = "http://localhost:8002/github/webhook"

# Example push event payload (simplified)
payload = {
    "ref": "refs/heads/main",
    "repository": {
        "id": 123456789,
        "name": "test-repo",
        "full_name": "owner/test-repo",
        "owner": {
            "login": "owner",
            "id": 12345
        },
        "html_url": "https://github.com/owner/test-repo",
        "created_at": "2023-01-01T00:00:00Z",
        "updated_at": "2023-01-02T00:00:00Z",
        "pushed_at": "2023-01-03T00:00:00Z",
        "default_branch": "main"
    },
    "after": "abcdef1234567890",
    "before": "0987654321fedcba",
    "commits": []
}

# Generate signature
payload_bytes = json.dumps(payload).encode('utf-8')
signature = "sha256=" + hmac.new(
    WEBHOOK_SECRET.encode('utf-8'),
    payload_bytes,
    hashlib.sha256
).hexdigest()

# Send webhook
response = requests.post(
    SENSOR_URL,
    data=payload_bytes,
    headers={
        "Content-Type": "application/json",
        "X-GitHub-Event": "push",
        "X-Hub-Signature-256": signature,
        "X-GitHub-Delivery": "test-delivery-" + str(int(time.time()))
    }
)

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")

# Wait a moment for processing
time.sleep(2)

# Now query for the event via KOI-net protocol
fetch_response = requests.post(
    "http://localhost:8002/koi-net/rids/fetch",
    json={"rid_types": ["orn:github.event"]}
)

rids = fetch_response.json().get("rids", [])
print(f"Found {len(rids)} GitHub events in sensor")
for rid in rids:
    print(f"  - {rid}")
```

### Backfill Operation Example

```python
import asyncio
import aiohttp
import json

async def trigger_and_monitor_backfill(repo_name):
    """Manually trigger and monitor backfill for a repository"""
    # This example assumes you have direct access to the sensor node's API
    # In a real implementation, you would need to communicate via the KOI-net protocol

    # First, get the current state
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://localhost:8002/koi-net/rids/fetch") as response:
            initial_data = await response.json()
            initial_count = len(initial_data.get("rids", []))
            print(f"Initial count of RIDs: {initial_count}")

        # Simulate triggering backfill (in practice this happens on node startup)
        # This is just illustrative - you would need to implement an API endpoint for this
        print(f"Triggering backfill for {repo_name}")

        # Wait for backfill to complete (simulated)
        await asyncio.sleep(10)

        # Check the results
        async with session.get(f"http://localhost:8002/koi-net/rids/fetch") as response:
            final_data = await response.json()
            final_count = len(final_data.get("rids", []))

            print(f"Final count of RIDs: {final_count}")
            print(f"Added {final_count - initial_count} new RIDs during backfill")

# Usage
asyncio.run(trigger_and_monitor_backfill("blockscience/koi-net"))
```

## Contributing

Contributions to the GitHub Sensor Node are welcome! Here's how to get started:

1. **Fork the Repository**
   - Create your own fork of the project on GitHub

2. **Clone Your Fork**
   ```bash
   git clone https://github.com/YOUR-USERNAME/github-sensor-node.git
   cd github-sensor-node
   ```

3. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

4. **Make Your Changes**
   - Implement your feature or bug fix
   - Write or update tests as necessary
   - Update documentation to reflect your changes

5. **Run Tests**
   ```bash
   pytest
   ```

6. **Format and Lint Your Code**
   ```bash
   black github_sensor_node
   flake8 github_sensor_node
   ```

7. **Commit Your Changes**
   ```bash
   git commit -m "Add your descriptive commit message"
   ```

8. **Push to GitHub**
   ```bash
   git push origin feature/your-feature-name
   ```

9. **Create a Pull Request**
   - Go to your fork on GitHub and click "New Pull Request"
   - Select your branch and provide a clear description of your changes

Please adhere to the existing code style and include appropriate tests for new functionality.

## Testing

The GitHub Sensor Node uses pytest for testing:

```bash
# Run all tests
pytest

# Run tests with coverage report
pytest --cov=github_sensor_node

# Generate HTML coverage report
pytest --cov=github_sensor_node --cov-report=html
```

For testing webhooks locally, you can use the GitHub webhook payload examples provided in the `tests/fixtures` directory.

## CI/CD & Deployment

The project uses GitHub Actions for continuous integration:

```yaml
name: GitHub Sensor Node CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.8, 3.9, "3.10"]

    steps:
    - uses: actions/checkout@v3
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"

    - name: Lint with flake8
      run: flake8 github_sensor_node

    - name: Check formatting with black
      run: black --check github_sensor_node

    - name: Test with pytest
      run: pytest
      env:
        GITHUB_TOKEN: ${{ secrets.TEST_GITHUB_TOKEN }}

    - name: Build package
      run: python -m build

    - name: Upload test artifacts
      uses: actions/upload-artifact@v3
      with:
        name: dist-${{ matrix.python-version }}
        path: dist/
```

For deployment, you can use Docker:

```yaml
name: Build and Push Docker Image

on:
  release:
    types: [published]

jobs:
  docker:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2

    - name: Login to DockerHub
      uses: docker/login-action@v2
      with:
        username: ${{ secrets.DOCKERHUB_USERNAME }}
        password: ${{ secrets.DOCKERHUB_TOKEN }}

    - name: Build and push
      uses: docker/build-push-action@v4
      with:
        context: .
        push: true
        tags: blockscience/github-sensor-node:latest,blockscience/github-sensor-node:${{ github.event.release.tag_name }}
```

## Versioning & Changelog

This project follows [Semantic Versioning](https://semver.org/):

- Major version (X.0.0): Incompatible API changes
- Minor version (0.X.0): New functionality in a backward-compatible manner
- Patch version (0.0.X): Backward-compatible bug fixes

For a detailed list of changes between versions, see the [CHANGELOG.md](CHANGELOG.md) file.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact & Support

### Maintainers
- BlockScience Team - [info@block.science](mailto:info@block.science)

### Get Help
- GitHub Issues: [Submit an issue](https://github.com/BlockScience/github-sensor-node/issues)
- Discussion: Join our [KOI-net community](https://github.com/BlockScience/koi-net/discussions)

### Community
- Follow us on Twitter: [@BlockScience](https://twitter.com/BlockScience)
- Visit our website: [block.science](https://block.science)
