# RFC-001 — Configuration des agents conversationnels et appel au MCP Habitation Jeunes

- **Statut** : Draft
- **Version du contrat** : 0.1.0
- **Public** : partenaires intégrant un agent LLM (OpenAI, Anthropic, Google, Mistral)
- **Portée** : ce document et ce dépôt décrivent **uniquement le contrat public**.
  L'implémentation réelle (couches de sécurité, backend, règles métier) est privée
  et hébergée par Acme.

## 1. Objet

Décrire comment configurer un agent conversationnel pour consommer le serveur MCP
de l'offre **Habitation Jeunes**, appeler les bons outils, gérer le **jeton lead**, et
respecter le **SLA** qui conditionne la conversion (un agent qui *fallback* perd le lead).

## 2. Vue d'ensemble

Le serveur expose **6 outils** via le protocole **MCP natif** (JSON-RPC 2.0,
transport *streamable HTTP*), sur l'endpoint `POST /mcp`. Seules les capacités
**tools** sont exposées (pas de `resources` ni `prompts`). L'agent :

1. ouvre une session (`ouvrir_session`) et récupère un `lead_token_ephemeral` ;
2. filtre chaque message et chaque réponse (`filtrer_message`, `filtrer_reponse`) ;
3. obtient le tarif et la fiche via les outils (jamais par calcul propre) ;
4. présente le `magic_link` de souscription.

Le détail du flux : voir [`session-flow.md`](./session-flow.md). Le contrat formel
des outils : voir [`../spec/tools.schema.json`](../spec/tools.schema.json).

## 3. Nommage et compatibilité

Le serveur s'expose sous le nom **`insurance_quote`** en **snake_case, sans tiret** :
le SDK Google Gemini rejette le caractère `-` dans un nom de serveur MCP. Utiliser
ce nom à l'identique chez tous les fournisseurs pour éviter les divergences.

## 4. Authentification

- **Aujourd'hui** : **HTTP Bearer**. Acme émet un jeton par partenaire ; il est
  transmis dans l'en-tête `Authorization: Bearer <token>` (ou le champ dédié du SDK).
  Le jeton est un secret : ne jamais le committer, l'injecter via un gestionnaire
  de secrets / variable d'environnement.
- **Cible** : **OAuth 2.1** (authorization code + PKCE, dynamic client registration).
- **Transport** : **HTTPS avec certificat valide obligatoire**. Certains clients
  (Mistral Le Chat) refusent un certificat auto-signé. L'endpoint partenaire d'Acme
  doit donc présenter un certificat d'AC publique/entreprise.

## 5. Configuration par fournisseur

Exemples complets et exécutables dans [`../examples/`](../examples/).

| Fournisseur | Mécanisme | Champ auth | Réf. |
| --- | --- | --- | --- |
| **Anthropic** | Messages API, `mcp_servers: [{type:"url", …}]` | `authorization_token` | `examples/anthropic_messages.py` |
| **OpenAI** | Responses API, `tools:[{type:"mcp", …}]` | `authorization` / en-tête | `examples/openai_responses.py` |
| **Google** | Gemini, SDK google-genai (MCP expérimental) | en-tête `Authorization` | `examples/google_genai.py` |
| **Mistral** | Le Chat / Studio, connecteur MCP personnalisé | Bearer (UI) / OAuth 2.1 | `examples/mistral_lechat.md` |

Dans tous les cas : restreindre explicitement la liste d'outils autorisés aux 6
outils du contrat (allowlist) et désactiver l'approbation humaine par appel quand
l'option existe (elle ajoute de la latence — voir §6).

## 6. SLA — pourquoi c'est déterminant pour la conversion

Les agents appliquent leur **propre délai d'attente** sur les appels d'outils. Si le
MCP est trop lent ou se bloque, l'agent **fallback** sur ses connaissances propres :
le parcours guidé est rompu et **le lead est perdu**. La disponibilité perçue prime
donc sur l'exhaustivité.

Le serveur applique un **budget de latence** (`X-SLA-Budget-Ms`, défaut **2500 ms**)
et garantit une **réponse dégradée rapide** plutôt qu'un blocage : en cas
d'indisponibilité interne, un résultat d'outil `statut = SERVICE_INDISPONIBLE` est
renvoyé immédiatement.

**Obligations côté agent :**

1. Sur `statut = SERVICE_INDISPONIBLE`, **restituer le message tel quel**. Ne jamais
   remplacer par une réponse inventée : c'est précisément ce qui « sauve » le lead
   pendant un incident (l'utilisateur est réorienté, pas désinformé).
2. Régler un **timeout client généreux** (recommandé **8000 ms**) pour laisser passer
   la réponse dégradée avant de couper.
3. **Désactiver l'approbation humaine** par appel d'outil (`require_approval: never`
   chez OpenAI, équivalents ailleurs) pour ne pas injecter de latence.
4. Ne pas mettre en place de ret/ry agressif : le serveur est déjà *fail-fast*.

En-têtes exposés : `X-Duration-Ms` (durée observée), `X-SLA-Budget-Ms` (budget),
`X-SLA-Breach: 1` (présent si dépassement).

## 7. Gestion des états

L'enveloppe MCP répond toujours HTTP 200 ; la décision applicative est portée par le
payload (`statut`, `code_equivalent`). Comportement attendu par statut : voir le
tableau de [`session-flow.md`](./session-flow.md). En résumé : respecter le
`HITL_SUSPENDED` (rediriger vers un conseiller), corriger sur `REFUS_VALIDATION`,
rouvrir une session sur `REFUS`, restituer tel quel sur `SERVICE_INDISPONIBLE`.

## 8. Ce qui n'est PAS exposé (et pourquoi)

Le contrat public ne révèle **aucune** mécanique interne : scoring de suspicion,
seuils, filtrage DLP, chaînage d'audit, kill switch, backend de tarification,
protections transport. Ces éléments sont volontairement absents de ce dépôt et du
mock : ils n'ont aucune utilité pour l'intégration partenaire et relèvent de la
sécurité d'Acme. Le mock renvoie des **données d'exemple** fictives.

## 9. Versionnement

Le contrat est versionné (`contract_version` dans `spec/server-info.json`). Toute
évolution incompatible (suppression d'outil, changement de schéma d'entrée) fera
l'objet d'une montée de version majeure et d'une communication aux partenaires. Les
ajouts rétrocompatibles (nouvel outil, champ de sortie optionnel) sont mineurs.

## 10. Support

Contact d'intégration : à compléter par Acme (canal partenaire, adresse, SLA support).
