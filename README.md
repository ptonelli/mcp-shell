# MCP Shell Server

A Model Context Protocol (MCP) server that provides shell execution and file system operations with **multi-conversation support** for LibreChat.

## ✨ New: Multi-Conversation Support

This version now supports proper session isolation per conversation when used with LibreChat. Each conversation gets its own working directory state, preventing conflicts between parallel conversations.

### How it works

The server now uses LibreChat's conversation ID (available via PR #9095) to create isolated sessions:
- Uses `{{LIBRECHAT_BODY_CONVERSATIONID}}` header to get unique conversation ID
- Each conversation maintains its own working directory state
- No more conflicts between parallel conversations in LibreChat

### LibreChat Configuration

Add this to your `librechat.yaml`:

```yaml
mcpServers:
  mcp-shell:
    type: sse
    url: http://localhost:8000
    headers:
      # This enables per-conversation isolation
      X-Conversation-ID: "{{LIBRECHAT_BODY_CONVERSATIONID}}"
      X-User-ID: "{{LIBRECHAT_USER_ID}}"
      X-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
    serverInstructions: |
      Shell execution server with per-conversation working directories.
      Each conversation maintains its own state and file system context.
```

### Debug Mode

Set `MCP_LOG_COMMANDS=1` to enable debug logging that shows:
- Context object inspection (all available attributes)
- Session ID resolution logic  
- Conversation ID detection from headers
- Working directory assignments

```bash
MCP_LOG_COMMANDS=1 python server.py
```

## Original Features
- read and write files and directories
- run code (at least python)
- install dependencies (uv or venv)

Now on how I want to do it: This should run on its own : no need for an
additional machine or API access. The LLM must not have the ability to run
containers. The setup must itself be running inside a container with a mounting
point for data to easily run on a home server.

# Organisation

2 sets of tools

- shell prompt
- code execution

# Shell prompt (WIP)

Just provide a shell prompt with the ability to set the current active directory.

# Python execution (WIP)

No complex security, the python code must run and the LLM must be able to add its own deps to run the code.

# Integration with Librechat

To integrate MCP Python with Librechat, you need to update the following configuration files:

## docker-compose.yml

Add the following service configuration to your docker-compose.yml:

```yaml
  mcp_python:
    container_name: mcp_python
    image: docker.nautil.org/mcp-python:latest
    environment:
      - WORKDIR=/home/projects
    volumes:
      - ./projects:/home/projects
```

## librechat.yaml

Add the following MCP server configuration to your librechat.yaml:

```yaml
mcpServers:
  python:
    type: streamable-http
    url: http://mcp_python:8000/mcp
```

This setup allows Librechat to interact with the MCP Python service, providing code execution and file management capabilities to your LLM.
