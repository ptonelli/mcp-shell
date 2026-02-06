import os
import difflib
from typing import Optional
from mcp.server.fastmcp import Context
from app.context import get_session_cwd, set_session_cwd, log_command
from app.security import is_safe_path
from app.config import WORKDIR

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
