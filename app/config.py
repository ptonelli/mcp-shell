import os
from pathlib import Path

# Get configuration from environment variables with defaults
WORKDIR = os.path.abspath(os.environ.get("WORKDIR", str(Path.home())))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 8000))

# Environment variable to control command logging
LOG_COMMANDS = os.environ.get("MCP_LOG_COMMANDS", "0").lower() in ("1", "true", "yes")
