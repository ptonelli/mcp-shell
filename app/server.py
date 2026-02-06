import os
from mcp.server.fastmcp import FastMCP
from app.config import WORKDIR, HOST, PORT
from app.tools.filesystem import cd, read_file, replace_lines
from app.tools.shell import shell_exec
from app.tools.git import clone_repo
from app.tools.media import get_image
from app.resources import list_projects, get_active_project

# Create an MCP server
mcp = FastMCP("shell", host=HOST, port=PORT)

# Register tools
mcp.tool()(cd)
mcp.tool()(read_file)
mcp.tool()(replace_lines)
mcp.tool()(shell_exec)
mcp.tool()(clone_repo)
mcp.tool()(get_image)

# Register resources
mcp.resource("projects://")(list_projects)
mcp.resource("active-project://")(get_active_project)

def run():
    TRANSPORT = os.environ.get("MCP_TRANSPORT", "streamable-http")
    print(f"Starting MCP-Shell on {HOST}:{PORT}, WORKDIR={WORKDIR}, TRANSPORT={TRANSPORT}")
    mcp.run(transport=TRANSPORT)
