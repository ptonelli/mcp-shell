import io
import os
import base64
import difflib
import mimetypes
import sys
import datetime
import subprocess
import shutil
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import ImageContent
from pathlib import Path
from typing import Dict, List, Optional, Union, Annotated, Any
from pydantic import Field

# Get configuration from environment variables with defaults
WORKDIR = os.path.abspath(os.environ.get("WORKDIR", str(Path.home())))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 8000))

# Environment variable to control command logging
LOG_COMMANDS = os.environ.get("MCP_LOG_COMMANDS", "0").lower() in ("1", "true", "yes")
# Global state to track current directory per session
session_directories: Dict[str, str] = {}

def debug_ctx(ctx: Context, operation: str = "unknown") -> str:
    """Debug function to examine all available attributes in Context object"""
    if not LOG_COMMANDS:
        return
        
    debug_info = {
        "operation": operation,
        "ctx_type": type(ctx).__name__,
        "ctx_dir": dir(ctx),
        "ctx_attrs": {}
    }
    
    # Examine all attributes
    for attr in dir(ctx):
        if not attr.startswith('_'):
            try:
                value = getattr(ctx, attr)
                if callable(value):
                    debug_info["ctx_attrs"][attr] = f"<method: {type(value).__name__}>"
                else:
                    debug_info["ctx_attrs"][attr] = str(value)[:200]  # Truncate long values
            except Exception as e:
                debug_info["ctx_attrs"][attr] = f"<error: {e}>"
    
    # Special attention to request_context
    if hasattr(ctx, 'request_context') and ctx.request_context:
        debug_info["request_context"] = {
            "type": type(ctx.request_context).__name__,
            "dir": dir(ctx.request_context),
            "attrs": {}
        }
        
        for attr in dir(ctx.request_context):
            if not attr.startswith('_'):
                try:
                    value = getattr(ctx.request_context, attr)
                    if callable(value):
                        debug_info["request_context"]["attrs"][attr] = f"<method: {type(value).__name__}>"
                    else:
                        debug_info["request_context"]["attrs"][attr] = str(value)[:200]
                        
                        # If it's a session object, dig deeper
                        if attr == 'session' and hasattr(value, '__dict__'):
                            debug_info["request_context"]["session_attrs"] = {}
                            for session_attr in dir(value):
                                if not session_attr.startswith('_'):
                                    try:
                                        session_value = getattr(value, session_attr)
                                        debug_info["request_context"]["session_attrs"][session_attr] = str(session_value)[:200]
                                    except Exception as e:
                                        debug_info["request_context"]["session_attrs"][session_attr] = f"<error: {e}>"
                                        
                except Exception as e:
                    debug_info["request_context"]["attrs"][attr] = f"<error: {e}>"
    
    timestamp = datetime.datetime.now().isoformat()
    print(f"[{timestamp}] [MCP-DEBUG-CTX] {debug_info}", file=sys.stdout)
    sys.stdout.flush()
    return "debug_completed"
def _get_session_key(ctx: Context) -> str:
    """Extract session key consistently using only conversation ID."""
    if hasattr(ctx, 'request_context') and ctx.request_context and hasattr(ctx.request_context, 'headers'):
        cid = ctx.request_context.headers.get('x-conversation-id') or ctx.request_context.headers.get('X-Conversation-ID')
        if cid:
            return f"conv_{cid}"
    return 'default'

def get_session_cwd(ctx: Context) -> str:
    debug_ctx(ctx, "get_session_cwd")
    session_id = _get_session_key(ctx)
    if session_id not in session_directories:
        session_directories[session_id] = WORKDIR
    return session_directories[session_id]

def set_session_cwd(ctx: Context, path: str):
    debug_ctx(ctx, "set_session_cwd")
    session_id = _get_session_key(ctx)
    session_directories[session_id] = os.path.abspath(path)

def log_command(command_type, command_data, result_success=None):
    """Log command execution to stdout if logging is enabled"""
    if LOG_COMMANDS:
        timestamp = datetime.datetime.now().isoformat()
        status = f"[{'SUCCESS' if result_success else 'FAILED'}]" if result_success is not None else ""
        print(f"[{timestamp}] [MCP-LOG] [{command_type}] {status} {command_data}", file=sys.stdout)
        sys.stdout.flush()

def is_safe_path(path: str) -> bool:
    """Check if the path is within the WORKDIR"""
    try:
        common = os.path.commonpath([WORKDIR, os.path.abspath(path)])
        return common == WORKDIR
    except (ValueError, Exception):
        return False

# Create an MCP server with environment variable configuration
mcp = FastMCP("shell", host=HOST, port=PORT)

@mcp.resource("projects://")
def list_projects() -> List[str]:
    """List all directories in the workdir."""
    log_command("resource", "list_projects")
    return [item for item in os.listdir(WORKDIR)
            if os.path.isdir(os.path.join(WORKDIR, item))]

@mcp.resource("active-project://")
def get_active_project(ctx: Context) -> str:
    """Get the active project name."""
    log_command("resource", "get_active_project")
    cwd = get_session_cwd(ctx)
    if cwd == WORKDIR:
        return "No active project"
    return os.path.basename(cwd)

@mcp.tool()
def cd(ctx: Context, directory: str) -> dict:
    """Change the session's current working directory."""
    log_command("cd", f"directory={directory}")
    current_dir = get_session_cwd(ctx)

    try:
        # Resolve target path
        if os.path.isabs(directory):
            target_path = os.path.normpath(directory)
        else:
            target_path = os.path.normpath(os.path.join(current_dir, directory))

        # Security check
        if not is_safe_path(target_path):
            return {
                "success": False,
                "message": f"Unauthorized path. Access is restricted to {WORKDIR}",
                "current_directory": current_dir,
                "error": "UnauthorizedPath"
            }

        if not os.path.isdir(target_path):
            return {
                "success": False,
                "message": f"Directory '{directory}' does not exist",
                "current_directory": current_dir,
                "error": "FileNotFoundError"
            }

        set_session_cwd(ctx, target_path)
        log_command("cd", f"directory={directory}", True)
        return {
            "success": True,
            "message": f"Successfully changed to directory '{target_path}'",
            "current_directory": target_path
        }
    except Exception as e:
        log_command("cd", f"directory={directory}", False)
        return {
            "success": False,
            "message": f"Failed to change directory: {str(e)}",
            "current_directory": current_dir,
            "error": type(e).__name__        }

@mcp.tool()
def get_image(
    ctx: Context,
    path: Annotated[str, Field(description="Path to the image file")]
) -> Union[ImageContent, dict]:
    """Get an image from the specified path, compressed if large."""
    cwd = get_session_cwd(ctx)
    abs_path = os.path.normpath(os.path.join(cwd, path))

    if not is_safe_path(abs_path):
        return {"success": False, "error": "Unauthorized path"}
    if not os.path.isfile(abs_path):
        return {"success": False, "error": f"File '{path}' not found"}

    try:
        mime_type, _ = mimetypes.guess_type(abs_path)
        if not mime_type or not mime_type.startswith('image/'):
            return {"success": False, "error": "Not a recognized image format"}

        file_size = os.path.getsize(abs_path)
        ext = os.path.splitext(abs_path)[1].lower().lstrip('.')
        if ext in ('jpg', 'jpeg'): ext = 'jpeg'

        if file_size > 1000000:
            from PIL import Image as PILImage
            buffer = io.BytesIO()
            img = PILImage.open(abs_path)
            img.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
            return Image(data=buffer.getvalue(), format="jpeg").to_image_content()
        else:
            with open(abs_path, 'rb') as f:
                return Image(data=f.read(), format=ext).to_image_content()
    except Exception as e:
        return {"success": False, "error": str(e)}

def detect_venv(cwd: str) -> str:
    """Detect if a Python virtual environment exists in the specified directory."""
    for venv_name in ["venv", ".venv", "env", ".env"]:
        venv_path = os.path.join(cwd, venv_name)
        activate = os.path.join(venv_path, "Scripts", "activate.bat") if sys.platform == "win32" \
                   else os.path.join(venv_path, "bin", "activate")
        if os.path.exists(activate):
            return venv_path
    return ""

@mcp.tool()
def shell_exec(ctx: Context, command: str, auto_env: bool = True) -> dict:
    """Execute a shell command in the session's current directory."""
    cwd = get_session_cwd(ctx)
    log_command("shell", f"command={command}, cwd={cwd}")

    venv_path = detect_venv(cwd) if auto_env else ""
    if venv_path:
        is_win = sys.platform == "win32"
        act = os.path.join(venv_path, "Scripts", "activate.bat") if is_win else os.path.join(venv_path, "bin", "activate")
        cmd = f'call "{act}" && {command}' if is_win else f'. "{act}" && {command}'
    else:
        cmd = command

    try:
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd
        )
        stdout, stderr = process.communicate()
        success = process.returncode == 0
        log_command("shell", f"command={command}", success)
        return {"stdout": stdout, "stderr": stderr, "success": success}
    except Exception as e:
        log_command("shell", f"command={command}", False)
        return {"stdout": "", "stderr": str(e), "success": False}

@mcp.tool()
def clone_repo(
    ctx: Context,
    url: str,
    reset: bool = False
) -> dict:
    """Clone a Git repository into WORKDIR and switch the session to it."""
    log_command("git_clone", f'url="{url}", reset={reset}')
    try:
        repo_name = url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"): repo_name = repo_name[:-4]
        
        target = os.path.normpath(os.path.join(WORKDIR, repo_name))
        if not is_safe_path(target):
            return {"success": False, "message": "Invalid repo target"}

        if os.path.isdir(target):
            if not reset:
                set_session_cwd(ctx, target)
                return {"success": True, "message": f"Switched to existing repo {repo_name}", "current_directory": target}
            shutil.rmtree(target)

        env = os.environ.copy()
        env['GIT_SSH_COMMAND'] = 'ssh -o StrictHostKeyChecking=no'
        r = subprocess.run(["git", "clone", url, repo_name], capture_output=True, text=True, env=env, cwd=WORKDIR)
        
        if r.returncode == 0:
            set_session_cwd(ctx, target)
            return {"success": True, "message": f"Cloned into {target}", "current_directory": target, "stdout": r.stdout}
        return {"success": False, "message": "Clone failed", "stderr": r.stderr}
    except Exception as e:
        return {"success": False, "message": str(e)}

@mcp.tool()
def read_file(
    ctx: Context,
    file_path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    show_line_numbers: bool = False
) -> dict:
    """Read specific lines from a file in the session's directory."""
    cwd = get_session_cwd(ctx)
    abs_path = os.path.normpath(os.path.join(cwd, file_path))
    
    if not is_safe_path(abs_path): return {"success": False, "error": "Unauthorized path"}
    if not os.path.isfile(abs_path): return {"success": False, "error": "File not found"}

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        total = len(lines)
        start = max(1, start_line)
        end = min(end_line or total, total)
        
        selected = lines[start-1:end]
        if show_line_numbers:
            width = len(str(end))
            content = "".join(f"{i:>{width}}: {l}" for i, l in enumerate(selected, start=start))
        else:
            content = "".join(selected)
            
        return {"success": True, "content": content, "total_lines": total, "lines_read": len(selected)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def replace_lines(
    ctx: Context,
    file_path: str,
    start_line: int,
    new_content: str,
    end_line: Optional[int] = None,
    dry_run: bool = False
) -> dict:
    """Replace or insert lines in a file.

    Args:
        start_line: Line number to start replacement (1-based)
        end_line: Line number to end replacement (1-based, inclusive). 
                 If None, only replaces start_line
        new_content: New content to insert (can be multi-line)
        dry_run: If True, show changes without applying them
    """
    cwd = get_session_cwd(ctx)
    abs_path = os.path.normpath(os.path.join(cwd, file_path))

    if not is_safe_path(abs_path):
        return {"success": False, "error": "Unauthorized path"}

    try:
        # Read existing file
        with open(abs_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        total_lines = len(lines)

        # Validate parameters
        if start_line < 1:
            return {"success": False, "error": "start_line must be >= 1"}
        if start_line > total_lines + 1:
            return {"success": False, "error": f"start_line {start_line} exceeds file length {total_lines}"}

        if end_line is None:
            end_line = start_line
        else:
            if end_line < start_line:
                return {"success": False, "error": "end_line must be >= start_line"}
            if end_line > total_lines:
                return {"success": False, "error": f"end_line {end_line} exceeds file length {total_lines}"}

        # Prepare new content with proper line endings
        if new_content == "":
            new_lines = []
        else:
            new_lines = new_content.splitlines(keepends=True)
            # If the last line doesn't end with \n, add it (unless new_content explicitly ended without \n)
            if new_lines and not new_lines[-1].endswith('\n') and new_content.endswith('\n'):
                new_lines[-1] += '\n'
            elif new_lines and not new_lines[-1].endswith('\n') and not new_content.endswith('\n'):
                # Content doesn't end with newline, but we need to preserve existing file structure
                # If we're not at the end of file, add newline
                if end_line < total_lines:
                    new_lines[-1] += '\n'

        # Create modified content
        modified = lines.copy()

        # Convert to 0-based indexing for array slicing
        start_idx = start_line - 1
        end_idx = end_line  # end_line is inclusive, so we don't subtract 1 for slicing

        # Replace the specified range
        modified[start_idx:end_idx] = new_lines

        # Generate diff
        diff = "".join(difflib.unified_diff(
            lines, modified,
            fromfile=f"{file_path} (before)",
            tofile=f"{file_path} (after)",
            lineterm=""
        ))

        # Apply changes if not dry run
        if not dry_run:
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.writelines(modified)

        lines_affected = end_line - start_line + 1
        lines_inserted = len(new_lines)

        return {
            "success": True,
            "diff": diff,
            "dry_run": dry_run,
            "lines_affected": lines_affected,
            "lines_inserted": lines_inserted,
            "operation": "insert" if start_line > total_lines else "replace"
        }

    except FileNotFoundError:
        return {"success": False, "error": f"File '{file_path}' not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@mcp.tool()
def debug_headers(ctx: Context) -> dict:
    """Debug tool to inspect the raw headers and context received from the client."""
    result = {
        "session_id": getattr(ctx, "session_id", None),
        "request_context_type": str(type(getattr(ctx, "request_context", None))),
        "request_context_type": str(ctx.request_context.request.headers),
        "headers": {}
    }

    if hasattr(ctx, "request_context") and ctx.request_context:
        if hasattr(ctx.request_context, "headers"):
            try:
                # Attempt to convert Headers object to dict
                result["headers"] = dict(ctx.request_context.headers)
            except Exception as e:
                result["headers"] = {"error": f"Could not convert headers: {str(e)}", "raw": str(ctx.request_context.headers)}
        else:
            result["headers"] = "No headers found in request_context"
    else:
         result["error"] = "No request_context found in ctx"

    return result

if __name__ == "__main__":
    os.chdir(WORKDIR)
    print(f"Starting MCP-Shell on {HOST}:{PORT}, WORKDIR={WORKDIR}")
    mcp.run(transport="streamable-http")
