import asyncio
import os
import sys
from mcp import ClientSession
from mcp.client.sse import sse_client

async def run_test():
    mcp_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8000/shell")
    print(f"--- Connection to: {mcp_url} ---")
    
    try:
        async with sse_client(mcp_url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                
                if "shell_exec" not in tool_names:
                    print(f"❌ Error: 'shell_exec' not found in {tool_names}")
                    sys.exit(1)

                print("--- Testing 'shell_exec' with 'ls' ---")
                result = await session.call_tool(
                    "shell_exec", 
                    arguments={"command": "ls", "auto_env": False}
                )

                output_text = "".join([c.text for c in result.content if hasattr(c, 'text')])

                if result.isError:
                    print(f"❌ Execution error: {output_text}")
                    sys.exit(1)
                
                print("✅ 'ls' executed successfully!")
                print(f"Output:\n{output_text}")
                print("--- SUCCESS ---")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_test())
