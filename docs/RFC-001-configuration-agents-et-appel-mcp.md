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

### 1.1 Positionnement stratégique — pourquoi MCP et rien de propriétaire

Ce serveur expose **exclusivement le protocole MCP natif** (JSON-RPC 2.0,
streamable HTTP), volontairement **agnostique du fournisseur** (Anthropic,
OpenAI, Google, Mistral, ou tout futur entrant). C'est un choix délibéré :

- **Aucun connecteur propriétaire ne sera développé.** Une intégration
  spécifique à un fournisseur (ex. un plugin/action propre à une plateforme)
  coûte à maintenir et diverge à chaque évolution de l'API du fournisseur.
  MCP étant un standard ouvert supporté nativement par l'ensemble des
  fournisseurs ciblés, c'est le seul point d'intégration proposé.
- **Les surfaces qui ne parlent pas MCP (ni function calling générique)
  sont explicitement hors périmètre.** C'est le cas par exemple des **Gems**
  Google (persona de l'app grand public gemini.google.com) : elles ne
  supportent aucun appel d'outil tiers en temps réel. Un agent Gemini doit
  passer par l'**API Gemini / Vertex AI** (function calling natif, support
  MCP expérimental — voir `examples/google_genai.py`) ; il n'y aura pas de
  pont spécifique construit pour contourner cette limitation côté Gems.
- **Ce serveur MCP est une solution d'attente**, le temps qu'une solution
  d'interopérabilité agent-à-agent (entre l'agent du client et l'agent
  d'Acme) soit disponible ; elle est en cours de réflexion et hors périmètre
  de ce dépôt. Le contrat MCP restera donc volontairement minimal plutôt que
  d'accumuler des adaptations propriétaires vouées à être remplacées.

## 2. Vue d'ensemble

Le serveur expose **7 outils** via le protocole **MCP natif** (JSON-RPC 2.0,
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

## 10. Routage réseau d'apport (code LP)

L'outil `obtenir_code_lp` détermine le code de landing page à utiliser pour la
souscription selon le réseau d'apport du client. Référentiel D'EXEMPLE (fictif,
comme le reste de ce dépôt) : [`../spec/referentiel-reseaux.json`](../spec/referentiel-reseaux.json).

**Règle impérative — mobilité du client :** un client peut rester rattaché au
réseau régional de son agence d'origine **même s'il déménage hors de ce
territoire**. Le département de résidence actuel n'est donc jamais une source
fiable à 100 % : il ne sert qu'à **estimer** le réseau quand le `code_reseau`
n'est pas déjà connu. En conséquence :

1. Si le `code_reseau` est connu (déclaré par le client ou fourni par un
   système amont), le transmettre : la résolution est alors **exacte**.
2. Sinon, transmettre le `departement` de résidence actuel : la résolution est
   **estimée** (`fiabilite = ESTIMEE_PAR_DEPARTEMENT`) et l'agent **ne doit
   jamais présenter ce résultat comme certain** — reformuler l'avertissement
   renvoyé, ou proposer à l'utilisateur de confirmer son réseau d'origine si
   l'exactitude est déterminante.
3. Si un département venait à être rattaché à plusieurs réseaux régionaux
   limitrophes (référentiel amené à évoluer), l'outil renvoie
   `fiabilite = INDETERMINEE`, un code LP de repli générique et la liste
   `code_reseau_candidats` : ne pas choisir arbitrairement entre les
   candidats, demander confirmation au client.
4. Certains réseaux sont **nationaux** (pas de notion de département) :
   résolution toujours **exacte** dès lors que le `code_reseau` est fourni.

## 11. Support

Contact d'intégration : à compléter par Acme (canal partenaire, adresse, SLA support).
