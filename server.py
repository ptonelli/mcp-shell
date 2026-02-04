import io
import os
import base64
import difflib
import mimetypes
import sys
import datetime
import subprocess
import shutil
from contextlib import redirect_stdout, redirect_stderr
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image
from pathlib import Path
from typing import Dict, List, Optional, Union, Annotated
from pydantic import Field

# Get configuration from environment variables with defaults
WORKDIR = os.environ.get("WORKDIR", str(Path.home()))
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", 8000))

# Environment variable to control command logging
# Use lower() to handle case-insensitivity
LOG_COMMANDS = os.environ.get("MCP_LOG_COMMANDS", "0").lower() in ("1", "true", "yes")

def log_command(command_type, command_data, result_success=None):
    """Log command execution to stdout if logging is enabled

    Args:
        command_type (str): Type of command (e.g., 'shell', 'python')
        command_data (str): The actual command that was executed
        result_success (bool, optional): Whether the command was successful
    """
    if LOG_COMMANDS:
        timestamp = datetime.datetime.now().isoformat()
        status = f"[{'SUCCESS' if result_success else 'FAILED'}]" if result_success is not None else ""
        print(f"[{timestamp}] [MCP-LOG] [{command_type}] {status} {command_data}", file=sys.stdout)
        sys.stdout.flush()  # Ensure logs are flushed immediately

# Create an MCP server with environment variable configuration
mcp = FastMCP("shell", host=HOST, port=PORT)

@mcp.resource("projects://")
def list_projects() -> List[str]:
    """
    List all directories in the workdir.

    Returns:
        List[str]: A list of directory names in the workdir.
    """
    log_command("resource", "list_projects")
    return [item for item in os.listdir(WORKDIR)
            if os.path.isdir(os.path.join(WORKDIR, item))]

@mcp.resource("active-project://")
def get_active_project() -> str:
    """
    Get the active project.

    Returns:
        str: The name of the active project or a message indicating no active project.
    """
    log_command("resource", "get_active_project")
    if os.getcwd() == WORKDIR:
        return "No active project"
    return os.path.basename(os.getcwd())  # Using basename instead of split[-1]

@mcp.tool()
def cd(directory: str) -> dict:
    """
    Change the current working directory.

    Args:
        directory (str): The directory path to change to.

    Returns:
        dict: A dictionary containing:
            - success (bool): Whether the operation was successful
            - message (str): An informative message about the result
            - current_directory (str): The current directory path
            - error (str, optional): Error details (if unsuccessful)
    """
    log_command("cd", f"directory={directory}")

    # Get the current directory before any changes
    current_dir = os.getcwd()

    try:
        # Handle absolute paths
        if os.path.isabs(directory):
            target_path = directory
            # Ensure the path is within WORKDIR for security
            if not target_path.startswith(WORKDIR):
                result = {
                    "success": False,
                    "message": f"Please provide either a relative path or a path in {WORKDIR}",
                    "current_directory": current_dir,
                    "error": "Unauthorized Path"
                }
                log_command("cd", f"directory={directory}", False)
                return result
        else:
            # Handle relative paths by resolving against current directory
            target_path = os.path.abspath(os.path.join(current_dir, directory))
            # Ensure the path is within WORKDIR for security
            if not target_path.startswith(WORKDIR):
                result = {
                    "success": False,
                    "message": f"The resulting path would be outside {WORKDIR}",
                    "current_directory": current_dir,
                    "error": "Unauthorized Path"
                }
                log_command("cd", f"directory={directory}", False)
                return result

        # Check if directory exists
        if not os.path.isdir(target_path):
            result = {
                "success": False,
                "message": f"Directory '{directory}' does not exist",
                "current_directory": current_dir,
                "error": "FileNotFoundError"
            }
            log_command("cd", f"directory={directory}", False)
            return result

        # Change to the directory
        os.chdir(target_path)
        result = {
            "success": True,
            "message": f"Successfully changed to directory '{directory}'",
            "current_directory": target_path
        }
        log_command("cd", f"directory={directory}", True)
        return result
    except Exception as e:
        # Get the current directory again after the exception
        # (it might have changed during the attempt)
        current_dir = os.getcwd()
        result = {
            "success": False,
            "message": f"Failed to change to directory '{directory}'",
            "current_directory": current_dir,
            "error": str(e)
        }
        log_command("cd", f"directory={directory}", False)
        return result

@mcp.tool()
def get_image(
    path: Annotated[str, Field(description="Path to the image file. If relative, resolves from current directory")]
) -> dict:
    """
    Get an image from the specified path.

    Returns the image as base64 data with appropriate metadata.
    Relative paths are resolved from the current working directory.
    """
    # Convert relative path to absolute path
    abs_path = os.path.abspath(path)

    # Check if the path exists
    if not os.path.exists(abs_path):
        return {"success": False, "error": f"Path '{path}' not found"}

    # Check if it's a file
    if not os.path.isfile(abs_path):
        return {"success": False, "error": f"Path '{path}' is not a file"}

    try:
        # Get file size in bytes
        file_size = os.path.getsize(abs_path)

        # Get the MIME type
        mime_type, _ = mimetypes.guess_type(abs_path)
        if not mime_type or not mime_type.startswith('image/'):
            return {"success": False, "error": f"File '{path}' is not a recognized image format"}

        # If file is larger than ~1MB, compress it
        if file_size > 1000000:
            buffer = io.BytesIO()

            # Open and compress the image
            img = Image.open(abs_path)
            img.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)

            # Use the compressed data
            img_data = buffer.getvalue()
            mime_type = "image/jpeg"  # Update mime type since we converted to JPEG
        else:
            # For smaller images, just read the file directly
            with open(abs_path, 'rb') as img_file:
                img_data = img_file.read()

        # Encode the image as base64
        img_base64 = base64.b64encode(img_data).decode('utf-8')

        # Determine format from the file extension
        format = os.path.splitext(abs_path)[1].lower().lstrip('.')
        if format in ('jpg', 'jpeg'):
            format = 'jpeg'

        # Return the Image object directly
        return Image(data=img_data, format=format)

    except Exception as e:
        return {"success": False, "error": str(e)}


# Helper function to detect virtual environments
def detect_venv() -> str:
    """
    Detect if a Python virtual environment exists in the current directory.

    Returns:
        str: Path to the virtual environment if found, empty string otherwise
    """

    # Common virtual environment directory names
    venv_names = ["venv", ".venv", "env", ".env", "virtualenv"]

    # Check current directory for common venv folders
    current_dir = os.getcwd()
    for venv_name in venv_names:
        venv_path = os.path.join(current_dir, venv_name)
        if os.path.isdir(venv_path):
            # Verify it's a valid venv by checking for activate script
            is_windows = sys.platform == "win32"
            if is_windows:
                activate_path = os.path.join(venv_path, "Scripts", "activate.bat")
            else:
                activate_path = os.path.join(venv_path, "bin", "activate")
            if os.path.exists(activate_path):
                return venv_path

    # No valid venv found
    return ""

def shell_exec_with_venv(venv_path: str, command: str) -> Dict[str, Union[str, bool]]:
    """
    Execute a shell command within an activated Python virtual environment.

    Args:
        venv_path (str): Path to the virtual environment directory
        command (str): The shell command to execute in the activated environment

    Returns:
        Dict[str, Union[str, bool]]: Dictionary with stdout, stderr and execution status
    """
    log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"")


    result = {
        "stdout": "",
        "stderr": "",
        "success": True
    }

    # Validate the venv path
    if not os.path.isdir(venv_path):
        result["success"] = False
        result["stderr"] = f"Error: Virtual environment directory '{venv_path}' does not exist."
        log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"", False)
        return result

    # Check if it looks like a valid venv (has bin/activate or Scripts/activate.bat)
    is_windows = sys.platform == "win32"
    if is_windows:
        activate_script = os.path.join(venv_path, "Scripts", "activate.bat")
    else:
        activate_script = os.path.join(venv_path, "bin", "activate")

    if not os.path.exists(activate_script):
        result["success"] = False
        result["stderr"] = f"Error: '{venv_path}' does not appear to be a valid virtual environment."
        log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"", False)
        return result

    try:
        # Construct the activation command based on OS
        if is_windows:
            cmd = f'call "{activate_script}" && {command}'
        else:  # Unix-like systems (Linux, macOS)
            cmd = f'. "{activate_script}" && {command}'

        # Run the command and capture output
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Get output and error streams
        stdout, stderr = process.communicate()

        # Populate result
        result["stdout"] = stdout
        result["stderr"] = stderr
        result["success"] = process.returncode == 0
        log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"", result["success"])

    except Exception as e:
        result["success"] = False
        result["stderr"] = f"Error executing command in virtual environment: {str(e)}"
        log_command("venv_shell", f"venv_path=\"{venv_path}\", command=\"{command}\"", False)

    return result

@mcp.tool()
def shell_exec(command: str, auto_env: bool = True) -> Dict[str, Union[str, bool]]:
    """
    Execute a shell command and return its output.
    Automatically uses virtual environment if detected and auto_env is True.

    Args:
        command (str): The shell command to execute
        auto_env (bool, optional): Whether to automatically use detected environments. Defaults to True.

    Returns:
        Dict[str, Union[str, bool]]: Dictionary with stdout, stderr and execution status
    """
    log_command("shell", f"command=\"{command}\", auto_env={auto_env}")

    # If auto_env is True, check for virtual environment
    if auto_env:
        venv_path = detect_venv()
        if venv_path:
            log_command("shell", f"Virtual environment detected at {venv_path}, using shell_exec_with_venv")
            return shell_exec_with_venv(venv_path, command)

    # Original shell_exec implementation

    result = {
        "stdout": "",
        "stderr": "",
        "success": True
    }

    try:
        # Run the command and capture output
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Get output and error streams
        stdout, stderr = process.communicate()

        # Populate result
        result["stdout"] = stdout
        result["stderr"] = stderr
        result["success"] = process.returncode == 0
        log_command("shell", f"command=\"{command}\"", result["success"])

    except Exception as e:
        result["success"] = False
        result["stderr"] = f"Error executing command: {str(e)}"
        log_command("shell", f"command=\"{command}\"", False)

    return result

@mcp.tool()
def clone_repo(
    url: Annotated[str, Field(description="Git repository URL to clone")],
    reset: Annotated[bool, Field(description="If True, delete any existing directory with the same repo name and re-clone. If False, just switch to the existing directory if present.")]=False,
) -> dict:
    """
    Clone a Git repository into WORKDIR and switch to its directory.

    - Always starts from WORKDIR.
    - Derives repo name from URL (last segment, strips .git).
    - If directory exists:
        - reset=False: just cd into it and return a note.
        - reset=True: delete and clone again.
    - If directory doesn't exist: clone and cd into it.
    """

    log_command("git_clone", f'url="{url}", reset={reset}')

    try:
        # Derive repo name - handle both SSH and HTTPS formats
        if ":" in url and "@" in url and not url.startswith("http"):
            # SSH format: git@host:path or git@host:user/repo
            tail = url.split(":")[-1].split("/")[-1]
        else:
            # HTTPS/file format
            tail = url.rstrip("/").split("/")[-1]
        repo_name = tail[:-4] if tail.endswith(".git") else tail

        # Very light sanity check
        if not repo_name or repo_name in (".", "..") or os.sep in repo_name or (os.altsep and os.altsep in repo_name):
            msg = f"Invalid repository name derived from URL: '{repo_name}'"
            log_command("git_clone", msg, False)
            return {"success": False, "message": msg, "current_directory": os.getcwd()}

        # Work from root (WORKDIR)
        os.chdir(WORKDIR)
        target = os.path.join(WORKDIR, repo_name)

        # If it exists and we don’t want to reset: just switch to it
        if os.path.isdir(target) and not reset:
            os.chdir(target)
            msg = f"Repository '{repo_name}' already exists. Switched to existing directory."
            log_command("git_clone", msg, True)
            return {"success": True, "message": msg, "current_directory": os.getcwd()}

        # If it exists and reset=True, remove it
        if os.path.isdir(target) and reset:
            try:
                shutil.rmtree(target)
            except Exception as e:
                msg = f"Failed to remove '{target}': {e}"
                log_command("git_clone", msg, False)
                return {"success": False, "message": msg, "current_directory": os.getcwd(), "stderr": str(e)}

        # always have an url which ends with .git (gitolite quirk fix)
        if not url.endswith(".git"):
            url = url + ".git"

        # Clone (either fresh or after reset)
        env = os.environ.copy()
        env['GIT_SSH_COMMAND'] = 'ssh -o StrictHostKeyChecking=no'
        r = subprocess.run(["git", "clone", url, repo_name], capture_output=True, text=True, env=env)
        if r.returncode != 0:
            msg = f"git clone failed with exit code {r.returncode}"
            log_command("git_clone", msg, False)
            # Stay in WORKDIR on failure
            return {
                "success": False,
                "message": msg,
                "current_directory": os.getcwd(),
                "stdout": r.stdout,
                "stderr": r.stderr,
            }

        # Switch to the cloned repo
        os.chdir(target)
        msg = ("Existing directory was replaced. " if reset else "") + f"Cloned '{url}' into '{target}'."
        log_command("git_clone", msg, True)
        return {
            "success": True,
            "message": msg,
            "current_directory": os.getcwd(),
            "stdout": r.stdout,
            "stderr": r.stderr,
        }

    except Exception as e:
        msg = f"Unexpected error during clone: {e}"
        log_command("git_clone", msg, False)
        return {"success": False, "message": msg, "current_directory": os.getcwd(), "stderr": str(e)}

@mcp.tool()
def read_file(
    file_path: str,
    start_line: int = 1,
    end_line: Optional[int] = None,
    show_line_numbers: bool = False
) -> dict:
    """
    Read specific lines from a file.

    Args:
        file_path (str): Path to the file to read (relative paths resolved from current directory)
        start_line (int): Starting line number (1-based indexing). Defaults to 1.
        end_line (int, optional): Ending line number (inclusive). If None, reads to end of file.
        show_line_numbers (bool): Whether to prepend line numbers to each line. Defaults to False.

    Returns:
        dict: A dictionary containing:
            - success (bool): Whether the operation was successful
            - message (str): An informative message about the result
            - content (str): The actual lines read from the file
            - total_lines (int): Total number of lines in the file
            - lines_read (int): Number of lines actually returned
            - start_line (int): The starting line number used
            - end_line (int): The ending line number used
            - show_line_numbers (bool): Whether line numbers were included
            - error (str, optional): Error details (if unsuccessful)
    """
    log_command("read_file", f"file_path='{file_path}', start_line={start_line}, end_line={end_line}, show_line_numbers={show_line_numbers}")

    # Convert relative path to absolute path
    abs_path = os.path.abspath(file_path)

    result = {
        "success": False,
        "message": "",
        "content": "",
        "total_lines": 0,
        "lines_read": 0,
        "start_line": start_line,
        "end_line": end_line,
        "show_line_numbers": show_line_numbers
    }

    # Validate start_line
    if start_line < 1:
        result["error"] = "start_line must be >= 1"
        result["message"] = f"Invalid start_line: {start_line}. Line numbers are 1-based."
        log_command("read_file", f"file_path='{file_path}'", False)
        return result

    # Validate end_line if provided
    if end_line is not None and end_line < start_line:
        result["error"] = "end_line must be >= start_line"
        result["message"] = f"Invalid range: start_line={start_line}, end_line={end_line}"
        log_command("read_file", f"file_path='{file_path}'", False)
        return result

    # Check if file exists
    if not os.path.exists(abs_path):
        result["error"] = "FileNotFoundError"
        result["message"] = f"File '{file_path}' does not exist"
        log_command("read_file", f"file_path='{file_path}'", False)
        return result

    # Check if it's a file (not a directory)
    if not os.path.isfile(abs_path):
        result["error"] = "NotAFileError"
        result["message"] = f"Path '{file_path}' is not a file"
        log_command("read_file", f"file_path='{file_path}'", False)
        return result

    try:
        with open(abs_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        result["total_lines"] = total_lines

        # Handle empty file
        if total_lines == 0:
            result["success"] = True
            result["message"] = "File is empty"
            result["content"] = ""
            result["lines_read"] = 0
            log_command("read_file", f"file_path='{file_path}'", True)
            return result

        # Adjust end_line if not specified or beyond file length
        actual_end_line = min(end_line or total_lines, total_lines)
        result["end_line"] = actual_end_line

        # Check if start_line is beyond file length
        if start_line > total_lines:
            result["success"] = True
            result["message"] = f"start_line ({start_line}) is beyond file length ({total_lines}). No lines returned."
            result["content"] = ""
            result["lines_read"] = 0
            log_command("read_file", f"file_path='{file_path}'", True)
            return result

        # Extract the requested lines (convert to 0-based indexing)
        selected_lines = all_lines[start_line-1:actual_end_line]

        # Generate content with or without line numbers
        if show_line_numbers:
            numbered_lines = []
            for i, line in enumerate(selected_lines, start=start_line):
                # Format line numbers with consistent width for better alignment
                line_num_width = len(str(actual_end_line))
                numbered_lines.append(f"{i:>{line_num_width}}: {line}")
            content = ''.join(numbered_lines)
        else:
            content = ''.join(selected_lines)

        result["success"] = True
        result["content"] = content
        result["lines_read"] = len(selected_lines)

        # Update message to indicate line numbering
        line_nums_msg = " (with line numbers)" if show_line_numbers else ""
        if start_line == 1 and actual_end_line == total_lines:
            result["message"] = f"Read entire file ({total_lines} lines){line_nums_msg}"
        else:
            result["message"] = f"Read lines {start_line}-{actual_end_line} ({len(selected_lines)} lines) from file with {total_lines} total lines{line_nums_msg}"

        log_command("read_file", f"file_path='{file_path}'", True)
        return result

    except UnicodeDecodeError as e:
        result["error"] = "UnicodeDecodeError"
        result["message"] = f"Cannot read file '{file_path}' as UTF-8 text: {str(e)}"
        log_command("read_file", f"file_path='{file_path}'", False)
        return result

    except PermissionError as e:
        result["error"] = "PermissionError"
        result["message"] = f"Permission denied reading file '{file_path}': {str(e)}"
        log_command("read_file", f"file_path='{file_path}'", False)
        return result

    except Exception as e:
        result["error"] = str(e)
        result["message"] = f"Unexpected error reading file '{file_path}': {str(e)}"
        log_command("read_file", f"file_path='{file_path}'", False)
        return result

@mcp.tool()
def replace_lines(
    file_path: str,
    start_line: int,
    new_content: str,
    end_line: Optional[int] = None,
    dry_run: bool = False
) -> dict:
    """
    Replace lines in a file by line number range, or insert if end_line is not provided.

    Args:
        file_path (str): Path to the file
        start_line (int): Starting line number (1-based)
        new_content (str): New content to replace/insert
        end_line (int, optional): Ending line number (1-based, inclusive). If None, inserts at start_line
        dry_run (bool): If True, shows what would change without modifying the file

    Returns:
        dict: Success status, message, and unified diff showing changes
    """
    try:
        # Read the original file
        with open(file_path, 'r', encoding='utf-8') as f:
            original_lines = f.readlines()

        total_lines = len(original_lines)

        # Validate line numbers
        if start_line < 1 or start_line > total_lines + 1:
            return {
                "success": False,
                "error": f"start_line {start_line} is out of range (file has {total_lines} lines)"
            }

        # Convert new_content to list of lines
        new_lines = new_content.split('\n')
        new_lines = [line + '\n' for line in new_lines[:-1]] + [new_lines[-1]]
        if new_content.endswith('\n'):
            new_lines[-1] += '\n'

        # Convert to 0-based indexing
        start_idx = start_line - 1

        if end_line is None:
            # INSERT mode
            operation = "insert"
            end_idx = start_idx
        else:
            # REPLACE mode
            if end_line < start_line or end_line > total_lines:
                return {
                    "success": False,
                    "error": f"end_line {end_line} is invalid (must be >= {start_line} and <= {total_lines})"
                }
            operation = "replace"
            end_idx = end_line

        # Create the modified version
        modified_lines = original_lines.copy()
        modified_lines[start_idx:end_idx] = new_lines

        # Generate unified diff (always show what changed/would change)
        diff_lines = list(difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"{file_path} (before)",
            tofile=f"{file_path} (after)",
            lineterm=''
        ))

        # Remove the file headers and format nicely
        if len(diff_lines) > 2:
            diff_output = '\n'.join(diff_lines[2:])  # Skip the --- and +++ lines
        else:
            diff_output = "No changes detected"

        if dry_run:
            # DRY RUN - don't modify the file
            return {
                "success": True,
                "message": f"[DRY RUN] Would {operation} at line {start_line}" + (f"-{end_line}" if end_line else ""),
                "diff": diff_output,
                "dry_run": True
            }
        else:
            # ACTUALLY MODIFY the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(modified_lines)

            return {
                "success": True,
                "message": f"Successfully {operation}ed at line {start_line}" + (f"-{end_line}" if end_line else ""),
                "diff": diff_output,
                "dry_run": False
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"Error processing {file_path}",
            "error": str(e)
        }

def initialize_workspace():
    """Initialize the workspace by setting an active project"""
    log_command("system", "initialize_workspace")

    # Get list of available projects
    projects = list_projects()

    os.chdir(WORKDIR)
    print(f"Setting '{WORKDIR}' as the active project")

if __name__ == "__main__":
    try:
        # Log startup information
        print(f"Command logging is {'ENABLED' if LOG_COMMANDS else 'DISABLED'}")

        initialize_workspace()
        print(f"Starting MCP server on {HOST}:{PORT}")
        print(f"Active project: {get_active_project()}")
        mcp.run(transport="sse")
    except KeyboardInterrupt:
        print("\nShutting down MCP server...")
        log_command("system", "shutdown", True)
        sys.exit(0)
