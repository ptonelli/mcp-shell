import os
import difflib
from typing import Optional
from mcp.server.fastmcp import Context
from app.context import get_session_cwd, set_session_cwd, log_command
from app.security import is_safe_path
from app.config import WORKDIR

# --- NAVIGATION & LECTURE ---

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
            "error": type(e).__name__
        }

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

# --- ÉDITION ROBUSTE (Remplace replace_lines) ---

def search_replace(
    ctx: Context,
    file_path: str,
    search: str,
    replace: str,
    occurrence: int = 1,
    dry_run: bool = False
) -> dict:
    """
    Replace text by searching for an exact match.
    This is much safer than line numbers.
    """
    cwd = get_session_cwd(ctx)
    abs_path = os.path.normpath(os.path.join(cwd, file_path))

    if not is_safe_path(abs_path): return {"success": False, "error": "Unauthorized path"}
    if not os.path.isfile(abs_path): return {"success": False, "error": f"File '{file_path}' not found"}

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            original = f.read()

        count = original.count(search)
        if count == 0:
            return {"success": False, "error": "Search text not found", "hint": _fuzzy_hint(original, search)}

        if occurrence != 0 and occurrence > count:
            return {"success": False, "error": f"Only {count} occurrences found, cannot replace n°{occurrence}"}

        # Replacement logic
        if occurrence == 0:
            modified = original.replace(search, replace)
            replaced_count = count
        else:
            modified = _replace_nth(original, search, replace, occurrence)
            replaced_count = 1

        # Generate diff
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile=f"a/{file_path}", tofile=f"b/{file_path}"
        ))

        if not dry_run:
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(modified)

        return {
            "success": True,
            "diff": diff,
            "occurrences_replaced": replaced_count,
            "dry_run": dry_run
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def insert_lines(
    ctx: Context,
    file_path: str,
    line_number: int,
    content: str,
    position: str = "after",
    dry_run: bool = False
) -> dict:
    """Insert text at a specific line without deleting existing code."""
    cwd = get_session_cwd(ctx)
    abs_path = os.path.normpath(os.path.join(cwd, file_path))

    if not is_safe_path(abs_path): return {"success": False, "error": "Unauthorized path"}
    if not os.path.isfile(abs_path): return {"success": False, "error": "File not found"}

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not content.endswith('\n'): content += '\n'
        new_content_lines = content.splitlines(keepends=True)

        # Calculate insertion index
        idx = line_number if position == "after" else max(0, line_number - 1)
        modified = lines[:idx] + new_content_lines + lines[idx:]

        diff = "".join(difflib.unified_diff(lines, modified, fromfile=f"a/{file_path}", tofile=f"b/{file_path}"))

        if not dry_run:
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.writelines(modified)

        return {"success": True, "diff": diff, "dry_run": dry_run}
    except Exception as e:
        return {"success": False, "error": str(e)}

def write_file(
    ctx: Context,
    file_path: str,
    content: str,
    overwrite: bool = False
) -> dict:
    """Create a new file or overwrite an existing one entirely."""
    cwd = get_session_cwd(ctx)
    abs_path = os.path.normpath(os.path.join(cwd, file_path))

    if not is_safe_path(abs_path): return {"success": False, "error": "Unauthorized path"}
    if os.path.exists(abs_path) and not overwrite:
        return {"success": False, "error": "File exists. Use overwrite=True to replace it."}

    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "message": f"File written to {file_path}", "size": len(content)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# --- HELPERS ---

def _replace_nth(text: str, search: str, replace: str, n: int) -> str:
    """Replaces the Nth occurrence of a string."""
    parts = text.split(search)
    if len(parts) <= n: return text
    return search.join(parts[:n]) + replace + search.join(parts[n:])

def _fuzzy_hint(original: str, search: str) -> str:
    """Returns a hint if the search failed but something similar exists."""
    search_lines = search.strip().splitlines()
    if not search_lines: return ""

    # Simple check for the first line of the search block
    for i, line in enumerate(original.splitlines()):
        if search_lines[0].strip() in line:
            return f"Search failed, but a similar line was found at line {i+1}. Check indentation/spaces."
    return "No similar text found. Use read_file to verify the exact content."
