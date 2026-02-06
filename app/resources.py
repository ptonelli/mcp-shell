import os
from typing import List
from mcp.server.fastmcp import Context
from app.context import get_session_cwd, log_command
from app.config import WORKDIR

def list_projects() -> List[str]:
    """List all directories in the workdir."""
    log_command("resource", "list_projects")
    return [item for item in os.listdir(WORKDIR)
            if os.path.isdir(os.path.join(WORKDIR, item))]

def get_active_project(ctx: Context) -> str:
    """Get the active project name."""
    log_command("resource", "get_active_project")
    cwd = get_session_cwd(ctx)
    if cwd == WORKDIR:
        return "No active project"
    return os.path.basename(cwd)
