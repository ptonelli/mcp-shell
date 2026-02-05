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

### LibreChat Configuration

Add this to your `librechat.yaml`. The `X-Conversation-ID` header is crucial for isolating file system states between different chats.

```yaml
mcpServers:
  mcp-shell:
    type: sse
    url: http://mcp-shell:8000/sse
    headers:
      # 🎯 KEY: This enables per-conversation isolation
      X-Conversation-ID: "{{LIBRECHAT_BODY_CONVERSATIONID}}"
      # Optional: User context for logging
      X-User-ID: "{{LIBRECHAT_USER_ID}}"
    
    serverInstructions: |
      Shell execution server with per-conversation working directories.
      Each conversation maintains its own isolated file system state.
      Capabilities: shell execution, file reading/writing, git cloning.
```

### Docker Compose Example

Add this service to your `docker-compose.yml`:

```yaml
services:
  mcp-shell:
    container_name: mcp-shell
    image: mcp-shell:latest
    build: .
    environment:
      - WORKDIR=/home/projects
      - HOST=0.0.0.0
      - PORT=8000
      - MCP_LOG_COMMANDS=1
    volumes:
      - ./projects:/home/projects
```

### Debug Mode

Set `MCP_LOG_COMMANDS=1` to enable debug logging that shows:
- Context object inspection (all available attributes)
- Session ID resolution logic  
- Conversation ID detection from headers
- Working directory assignments

To run locally with debug logging:
```bash
MCP_LOG_COMMANDS=1 python server.py
```

## Features
- **Session Isolation**: Each LibreChat conversation gets its own working directory.
- **File Operations**: Read, write, list files with path security checks.
- **Shell Execution**: Run shell commands (supports Python venvs detection).
- **Git Support**: Clone repositories and switch context automatically.
