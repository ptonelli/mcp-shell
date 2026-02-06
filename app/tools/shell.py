import os
import sys
import subprocess
from mcp.server.fastmcp import Context
from app.context import get_session_cwd, log_command

def detect_venv(cwd: str) -> str:
    """Detect if a Python virtual environment exists in the specified directory."""
    for venv_name in ["venv", ".venv", "env", ".env"]:
        venv_path = os.path.join(cwd, venv_name)
        activate = os.path.join(venv_path, "Scripts", "activate.bat") if sys.platform == "win32" \
                   else os.path.join(venv_path, "bin", "activate")
        if os.path.exists(activate):
            return venv_path
    return ""

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
