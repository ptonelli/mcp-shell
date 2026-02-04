import pytest
import subprocess
import sys
import os

import time
import signal
import tempfile
import shutil
from pathlib import Path

# Port utilisé pour les tests (différent de la prod 8000 par sécurité)
TEST_PORT = 8001
TEST_HOST = "127.0.0.1"
SERVER_URL = f"http://{TEST_HOST}:{TEST_PORT}"

@pytest.fixture(scope="session")
def test_workdir():
    """Crée un dossier de travail temporaire pour toute la session de test"""
    # Créer un dossier temporaire
    temp_dir = tempfile.mkdtemp(prefix="mcp_test_")
    yield temp_dir
    # Nettoyage après les tests
    shutil.rmtree(temp_dir)

@pytest.fixture(scope="session")
def mcp_server(test_workdir):
    """Lance le serveur MCP en arrière-plan"""
    
    # Définir l'environnement pour le serveur de test
    env = os.environ.copy()
    env["PORT"] = str(TEST_PORT)
    env["HOST"] = TEST_HOST
    env["WORKDIR"] = test_workdir
    env["MCP_LOG_COMMANDS"] = "1"
    
    # Lancer le serveur comme sous-processus
    print(f"\\n[SETUP] Démarrage du serveur MCP sur le port {TEST_PORT}...")
    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Attendre que le serveur soit prêt (polling simple)
    import httpx
    started = False
    retries = 20
    
    for _ in range(retries):
        try:            # On tente de récupérer le SSE handshake (GET)
            # FastMCP expose /sse
            # On utilise stream=True pour ne pas bloquer sur le flux SSE infini
            with httpx.stream("GET", f"{SERVER_URL}/sse", timeout=1.0) as response:
                if response.status_code == 200:
                    started = True
                    break
        except (httpx.RequestError, Exception):
            time.sleep(0.5)
            
    if not started:
        # Si échec, on lit les logs pour debug
        print(f"\\n[ERROR] Timeout lors de la connexion au serveur. Tentative de récupération des logs...")
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            
        print(f"STDOUT: {stdout}\\nSTDERR: {stderr}")
        pytest.fail("Le serveur MCP n'a pas démarré dans les temps.")

    print(f"[SETUP] Serveur démarré.")
    yield SERVER_URL    
    # Teardown : Arrêt du serveur
    print(f"\\n[TEARDOWN] Arrêt du serveur...")
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()

@pytest.fixture
async def client_session(mcp_server):
    """

    Crée une session client MCP connectée au serveur de test.
    Nécessite 'mcp' installé.
    """
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client
    
    # Utilisation du gestionnaire de contexte sse_client
    async with sse_client(f"{mcp_server}/sse") as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            yield session

import pytest
import pytest_asyncio
import subprocess
import sys
import os

import time
import signal
import tempfile
import shutil
