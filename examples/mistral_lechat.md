# Mistral — connecteur MCP personnalisé (Le Chat) et La Plateforme

Doc : https://docs.mistral.ai/le-chat/knowledge-integrations/connectors/mcp-connectors

## Le Chat — connecteur MCP personnalisé (UI, sans code)

1. Ouvrir **Connectors** → **+ Add Connector** → onglet **Custom MCP Connector**.
2. Renseigner :
   - **Connector name** : `insurance_quote` (sans espace ni caractère spécial).
   - **Server URL** : `https://mcp.example.com/mcp`.
   - **Description** (optionnel) : « Devis Habitation Jeunes — Acme ».
3. **Authentification** : Le Chat détecte la méthode automatiquement.
   - Aujourd'hui : **HTTP Bearer Token** (jeton émis par Acme).
   - Cible : **OAuth 2.1** (avec dynamic client registration).

> **Exigence technique** : le serveur doit être accessible en **HTTPS avec un
> certificat TLS valide** (une AC interne / certificat auto-signé est refusé).
> C'est un point d'attention côté déploiement Acme pour l'ouverture partenaire.

## La Plateforme / Studio (par API)

Le principe est identique : déclarer le serveur MCP distant (URL + en-tête
`Authorization: Bearer …`) et restreindre la liste d'outils à :
`ouvrir_session`, `filtrer_message`, `filtrer_reponse`, `obtenir_tarif`,
`obtenir_details_mrh`, `verifier_discount`, `obtenir_code_lp`. Se reporter à la
doc Studio pour la signature exacte de l'appel, susceptible d'évoluer.
