# 🎯 Solution: Obtenir le Conversation ID côté MCP dans LibreChat

## 📋 Résumé du problème
- Le serveur MCP avait une limitation avec plusieurs contextes en parallèle
- Le `context_id` restait constant entre différentes conversations LibreChat
- Impossible de différencier les sessions/conversations côté MCP

## ✅ Solution trouvée

### 🔍 Dans la documentation LibreChat
**PR #9095** (mergée) : "Request Placeholders for Custom Endpoint & MCP Headers"

Ajoute de nouveaux placeholders pour les headers MCP :
- `{{LIBRECHAT_BODY_CONVERSATIONID}}` - **ID unique de conversation** 🎯
- `{{LIBRECHAT_BODY_PARENTMESSAGEID}}` - ID du message parent  
- `{{LIBRECHAT_BODY_MESSAGEID}}` - ID du message actuel

### 📚 Documentation officielle
- [MCP Servers Object Structure](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_servers)
- [Issue #8017: Thread Id in MCP headers](https://github.com/danny-avila/LibreChat/issues/8017)
- [PR #9095: Request Placeholders](https://github.com/danny-avila/LibreChat/pull/9095)

## 🛠 Implémentation

### 1. Configuration LibreChat (`librechat.yaml`)

```yaml
mcpServers:
  mcp-shell:
    type: sse
    url: http://localhost:8000
    headers:
      # 🔑 CLÉ : Ceci active l'isolation par conversation
      X-Conversation-ID: "{{LIBRECHAT_BODY_CONVERSATIONID}}"
      
      # Optionnel : contexte utilisateur
      X-User-ID: "{{LIBRECHAT_USER_ID}}"
      X-User-Email: "{{LIBRECHAT_USER_EMAIL}}"
    
    serverInstructions: |
      Serveur shell avec répertoires de travail par conversation.
      Chaque conversation maintient son propre état isolé.
```

### 2. Modifications côté serveur MCP

**Nouvelle logique de session** dans `server.py` :
- Lecture du header `X-Conversation-ID` 
- Utilisation de `conv_{conversationId}` comme identifiant de session
- Fallback sur l'ancienne logique si pas de conversation ID
- Session isolée par conversation

**Fonction debug** ajoutée :
- Inspection complète de l'objet `Context`
- Affichage des headers disponibles
- Debugging de la résolution des sessions

### 3. Activation du debug

```bash
# Active les logs de debug
MCP_LOG_COMMANDS=1 python server.py

# Les logs affichent :
# - Tous les attributs du contexte
# - Headers reçus
# - Résolution des IDs de session
# - Attribution des répertoires de travail
```

## 🎁 Résultat

**Avant** : Toutes les conversations partageaient le même répertoire de travail
**Après** : Chaque conversation LibreChat a son propre répertoire de travail isolé

Exemple de sessions créées :
- Conversation 1: `session_directories["conv_abc123"]` = `/home/user/project1`
- Conversation 2: `session_directories["conv_def456"]` = `/home/user/project2`
- Fallback: `session_directories["default"]` = `/home/user/workdir`

## 📁 Fichiers modifiés

1. **`server.py`**
   - Fonction `debug_ctx()` pour inspection du contexte
   - Logique mise à jour dans `get_session_cwd()` et `set_session_cwd()`
   - Support des headers `X-Conversation-ID`

2. **`librechat-config-example.yaml`**
   - Configuration complète avec placeholders
   - Instructions pour l'agent
   - Paramètres optimaux

3. **`README.md`**
   - Documentation du support multi-conversation
   - Guide d'utilisation et de debug

## 🚀 Test de la solution

1. Démarrer le serveur MCP avec debug:
   ```bash
   MCP_LOG_COMMANDS=1 python server.py
   ```

2. Configurer LibreChat avec le placeholder `{{LIBRECHAT_BODY_CONVERSATIONID}}`

3. Ouvrir 2 conversations différentes dans LibreChat

4. Dans chaque conversation, exécuter :
   ```
   cd /tmp && pwd
   ```

5. Vérifier que chaque conversation garde son propre répertoire de travail

## 💡 Avantages

- ✅ Isolation complète entre conversations
- ✅ Support multi-utilisateur maintenu
- ✅ Rétrocompatibilité (fallback sur ancienne logique)
- ✅ Debug complet pour troubleshooting
- ✅ Configuration simple côté LibreChat
