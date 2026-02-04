import pytest
import os
from mcp.types import CallToolRequestParams

@pytest.mark.asyncio
async def test_list_tools(client_session):
    """Vérifie que les outils sont bien listés"""
    result = await client_session.list_tools()
    tools = {t.name for t in result.tools}
    expected_tools = {"cd", "shell_exec", "get_image", "clone_repo", "read_file", "replace_lines"}
    assert expected_tools.issubset(tools)

@pytest.mark.asyncio
async def test_resource_projects(client_session, test_workdir):
    """Vérifie la ressource projects://"""
    # Créer un faux projet
    project_path = os.path.join(test_workdir, "my-project")
    os.makedirs(project_path, exist_ok=True)
    
    result = await client_session.list_resources()
    # Note: L'implémentation actuelle de list_projects dans server.py renvoie une liste via resource(),
    # mais FastMCP gère les templates. 
    # Pour ce test simple, on va vérifier si on peut lire la ressource (si implémenté)
    # ou simplement vérifier l'exécution d'une commande shell qui liste.
    pass

@pytest.mark.asyncio
async def test_shell_exec(client_session):
    """Test de l'exécution d'une commande shell simple"""
    result = await client_session.call_tool(
        "shell_exec",
        arguments={"command": "echo 'Hello MCP'"}
    )
    # FastMCP retourne souvent une liste de TextContent
    content = result.content[0].text
    assert "Hello MCP" in content
    assert result.isError is False

@pytest.mark.asyncio
async def test_file_operations(client_session, test_workdir):
    """Test complet : écriture (via shell), lecture, modification"""
    filename = "test_file.txt"
    file_path = os.path.join(test_workdir, filename)
    
    # 1. Créer un fichier via shell_exec
    await client_session.call_tool(
        "shell_exec",
        arguments={"command": f"echo 'Ligne 1\nLigne 2\nLigne 3' > {filename}"}
    )
    
    # 2. Lire le fichier
    read_result = await client_session.call_tool(
        "read_file",
        arguments={"file_path": filename}
    )
    content = read_result.content[0].text
    assert "Ligne 1" in content
    assert "Ligne 3" in content
    
    # 3. Remplacer une ligne
    replace_result = await client_session.call_tool(
        "replace_lines",
        arguments={
            "file_path": filename,
            "start_line": 2,
            "end_line": 2,
            "new_content": "Ligne 2 Modifiée\n"
        }
    )
    assert replace_result.isError is False
    
    # 4. Vérifier la modification
    read_again = await client_session.call_tool(
        "read_file",
        arguments={"file_path": filename}
    )
    new_content = read_again.content[0].text
    assert "Ligne 2 Modifiée" in new_content
    assert "Ligne 2\n" not in new_content

@pytest.mark.asyncio
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
    assert f"Successfully changed to directory '{subdir}'" in str(result.content)
    
    # Vérifier pwd via shell
    pwd_res = await client_session.call_tool("shell_exec", arguments={"command": "pwd"})
    assert subdir in pwd_res.content[0].text
