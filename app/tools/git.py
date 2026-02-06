import os
import shutil
import subprocess
from mcp.server.fastmcp import Context
from app.context import set_session_cwd, log_command
from app.security import is_safe_path
from app.config import WORKDIR

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
