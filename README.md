# Acme Habitation Jeunes — Contrat d'intégration MCP (partenaires LLM)

Dépôt **public** d'intégration pour connecter un agent conversationnel
(OpenAI, Anthropic, Google, Mistral) au serveur MCP de l'offre **Habitation Jeunes**
d'Acme Assurances.

> Ce dépôt contient **uniquement le contrat public** : la liste des outils, leurs
> schémas, le flux de session/jeton, un **serveur mock** exécutable pour développer
> en local, et des exemples de configuration par fournisseur.
>
> Il ne contient **aucune** logique métier réelle, aucune couche de sécurité, aucun
> secret et aucune donnée de production. Le serveur MCP réel d'Acme est hébergé et
> distinct de ce dépôt.

## Contenu

| Chemin | Rôle |
| --- | --- |
| `docs/RFC-001-configuration-agents-et-appel-mcp.md` | RFC : configuration des agents + appel au MCP |
| `docs/session-flow.md` | Cycle de vie d'une session et du jeton lead |
| `spec/tools.schema.json` | Contrat formel versionné des 6 outils (entrées/sorties) |
| `spec/server-info.json` | Métadonnées du serveur (nom, version, transport) |
| `mock_server/server.py` | Serveur MCP **mock** exécutable (réponses d'exemple) |
| `examples/` | Configurations prêtes à l'emploi par fournisseur |

## Démarrage rapide (serveur mock)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m mock_server.server            # écoute sur http://127.0.0.1:8000/mcp
```

Le mock parle le **protocole MCP natif** (JSON-RPC 2.0, transport *streamable HTTP*),
exactement comme le serveur réel. Il renvoie des **données d'exemple** clairement
marquées et **n'applique aucune règle de sécurité** — il sert à valider votre
intégration (découverte des outils, enchaînement des appels, gestion du jeton).

## Les 6 outils exposés

1. `ouvrir_session` — ouvre une session anonyme, renvoie le `lead_token_ephemeral` + le disclaimer IA.
2. `filtrer_message` — à appeler sur chaque message utilisateur **avant** traitement.
3. `filtrer_reponse` — à appeler sur chaque réponse **avant** restitution à l'utilisateur.
4. `obtenir_tarif` — tarif officiel Habitation Jeunes (jamais calculé côté agent).
5. `obtenir_details_mrh` — fiche produit.
6. `verifier_discount` — remise d'orientation (aucun code promo).

## Nom du serveur

Le serveur s'expose sous le nom **`insurance_quote`** (snake_case, sans tiret) pour la
compatibilité avec l'ensemble des SDK partenaires (Google Gemini refuse le `-`).

## Statut

Contrat `v0` — susceptible d'évoluer. Voir la RFC pour la politique de versionnement.
Ce mock est fourni « en l'état » à des fins d'intégration (licence MIT).
