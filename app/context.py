import os
import sys
import datetime
from typing import Dict
from mcp.server.fastmcp import Context
from app.config import WORKDIR, LOG_COMMANDS

# Global state to track current directory per session
session_directories: Dict[str, str] = {}

def _get_session_key(ctx: Context) -> str:
    """Extract session key consistently using only conversation ID."""
    try:
        if hasattr(ctx, 'request_context') and ctx.request_context:
            # Headers are located in request_context.request.headers
            if hasattr(ctx.request_context, 'request') and hasattr(ctx.request_context.request, 'headers'):
                headers = ctx.request_context.request.headers
                cid = headers.get('x-conversation-id') or headers.get('X-Conversation-ID')
                if cid:
                    return f"conv_{cid}"
    except Exception:
        pass
    return 'default'

def get_session_cwd(ctx: Context) -> str:
    session_id = _get_session_key(ctx)
    if session_id not in session_directories:
        session_directories[session_id] = WORKDIR
    return session_directories[session_id]

def set_session_cwd(ctx: Context, path: str):
    session_id = _get_session_key(ctx)
    session_directories[session_id] = os.path.abspath(path)

def log_command(command_type, command_data, result_success=None):
    """Log command execution to stdout if logging is enabled"""
    if LOG_COMMANDS:
        timestamp = datetime.datetime.now().isoformat()
        status = f"[{'SUCCESS' if result_success else 'FAILED'}]" if result_success is not None else ""
        print(f"[{timestamp}] [MCP-LOG] [{command_type}] {status} {command_data}", file=sys.stdout)
        sys.stdout.flush()
