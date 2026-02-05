import pytest
import os
import json
from mcp.types import CallToolRequestParams

@pytest.mark.anyio
async def test_list_tools(client_session):
    """Vérifie que les outils sont bien listés"""
    result = await client_session.list_tools()
    tools = {t.name for t in result.tools}
    expected_tools = {"cd", "shell_exec", "get_image", "clone_repo", "read_file", "replace_lines"}
    assert expected_tools.issubset(tools)


@pytest.mark.anyio
async def test_shell_exec(client_session):
    """Test de l'exécution d'une commande shell simple"""
    result = await client_session.call_tool(
        "shell_exec",
        arguments={"command": "echo 'Hello MCP'"}
    )
    # FastMCP retourne souvent une liste de TextContent
    content = result.content[0].text
    
    # Le serveur retourne du JSON
    try:
        data = json.loads(content)
        assert "Hello MCP" in data["stdout"]
        assert data["success"] is True
    except json.JSONDecodeError:
        assert "Hello MCP" in content

    assert result.isError is False

@pytest.mark.anyio
async def test_file_operations(client_session, test_workdir):
    """Test complet : écriture (via shell), lecture, modification"""
    filename = "test_file.txt"
    file_path = os.path.join(test_workdir, filename)
    
    # 1. Créer un fichier via shell_exec
    await client_session.call_tool(
        "shell_exec",
        arguments={"command": f"echo 'Ligne 1\\nLigne 2\\nLigne 3' > {filename}"}
    )
    
    # 2. Lire le fichier
    read_result = await client_session.call_tool(
        "read_file",
        arguments={"file_path": filename}
    )
    content_read = read_result.content[0].text
    
    # read_file retourne aussi du JSON
    try:
        data = json.loads(content_read)
        text_content = data["content"]
    except json.JSONDecodeError:
        text_content = content_read
        
    assert "Ligne 1" in text_content
    assert "Ligne 3" in text_content
    
    # 3. Remplacer une ligne
    replace_result = await client_session.call_tool(
        "replace_lines",
        arguments={
            "file_path": filename,
            "start_line": 2,
            "end_line": 2,
            "new_content": "Ligne 2 Modifiée\\n"
        }
    )
    assert replace_result.isError is False
    
    # 4. Vérifier la modification
    read_again = await client_session.call_tool(
        "read_file",
        arguments={"file_path": filename}
    )
    new_content_read = read_again.content[0].text
    
    try:
        new_data = json.loads(new_content_read)
        new_text_content = new_data["content"]
    except json.JSONDecodeError:
        new_text_content = new_content_read
        
    assert "Ligne 2 Modifiée" in new_text_content
    assert "Ligne 2\\n" not in new_text_content

@pytest.mark.anyio
async def test_cd_tool(client_session, test_workdir):
    """Test du changement de répertoire"""
    # Créer un sous-dossier
    subdir = "subdir"
    os.makedirs(os.path.join(test_workdir, subdir), exist_ok=True)
    
    # CD dans le sous-dossier
    result = await client_session.call_tool(
        "cd",
        arguments={"directory": subdir}
    )
    assert result.isError is False
    
    # Parsing JSON result
    content = json.loads(result.content[0].text)
    assert content["success"] is True
    assert subdir in content["message"]


    
    # Vérifier pwd via shell
    pwd_res = await client_session.call_tool("shell_exec", arguments={"command": "pwd"})
    pwd_content = pwd_res.content[0].text
    try:
        pwd_data = json.loads(pwd_content)
        pwd_text = pwd_data["stdout"]
    except json.JSONDecodeError:
        pwd_text = pwd_content
        
    assert subdir in pwd_text


@pytest.mark.anyio
async def test_get_image(client_session, test_workdir):
    """Test get_image tool"""
    filename = "test.png"
    file_path = os.path.join(test_workdir, filename)
    with open(file_path, "wb") as f:
        f.write(b"fake image data")
        
    result = await client_session.call_tool(
        "get_image",
        arguments={"path": filename}
    )
    
    assert result.isError is False
    assert len(result.content) > 0
    assert result.content[0].type == "image"

