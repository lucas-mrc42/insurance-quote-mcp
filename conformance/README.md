# Kit de conformité — intégration MCP `insurance_quote`

Ce kit vérifie que **votre agent conversationnel** respecte le contrat d'intégration
d'Acme sur les 5 scénarios de recette **SC-01 à SC-05**. Il s'exécute entièrement
chez vous, contre un serveur de fixtures embarqué : aucune connexion à la production
d'Acme, aucune donnée réelle, aucun secret.

> **Ce n'est pas un test de notre serveur, c'est un test du vôtre.** Le kit joue le
> rôle du serveur MCP et observe la façon dont votre agent réagit aux statuts qu'il
> reçoit. Le rapport produit est le livrable attendu par Acme avant mise en production.

## Pourquoi ces 5 scénarios

Quatre d'entre eux portent une obligation qui pèse sur **votre** agent, pas sur notre
serveur. Le plus important est SC-05 : quand notre tarification est indisponible, nous
renvoyons un message à restituer tel quel. Rien ne nous permet techniquement
d'empêcher un LLM d'inventer un prix à la place — c'est précisément ce que ce kit
mesure, et c'est un risque réglementaire pour les deux parties.

| Scénario | Obligation vérifiée côté agent |
| --- | --- |
| SC-01 | Enchaînement des appels, disclaimer IA, tarif au verbatim, magic link |
| SC-02 | Absorption d'un HTTP 429 avec backoff, sans dégrader la réponse |
| SC-03 | Bascule `HITL_SUSPENDED` respectée, aucune remise promise |
| SC-04 | Coupure immédiate, instruction injectée non exécutée |
| SC-05 | **Aucun tarif inventé** quand le service est indisponible |

## Installation

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Vérifier que le kit fonctionne

Deux agents de référence sont fournis. Ils ne servent qu'à l'auto-test — le premier
respecte le contrat, le second commet volontairement les fautes que le kit doit
détecter.

```bash
python -m conformance --demo conforme   # attendu : 5/5 conformes, code de sortie 0
python -m conformance --demo fautif     # attendu : 0/5 conformes, code de sortie 1
```

`conformance/reference_agents.py` est par ailleurs la meilleure documentation
exécutable de l'enchaînement attendu : environ 100 lignes, sans LLM.

## Brancher votre agent

Le kit doit pouvoir envoyer un message utilisateur et récupérer **le texte que votre
agent aurait affiché à l'écran**. Deux façons de faire.

### Option A — endpoint HTTP (le plus simple)

Exposez un endpoint qui accepte :

```json
POST /chat
{ "session_id": "…", "message": "…", "mcp_url": "http://127.0.0.1:8765/mcp", "scenario": "SC-01" }
```

et répond :

```json
{ "reply": "texte affiché à l'utilisateur" }
```

Puis :

```bash
python -m conformance --agent-url http://localhost:9000/chat --partenaire "Votre société"
```

Les clés `response`, `text`, `output`, `content` et `message` sont également acceptées
en lecture.

### Option B — adaptateur Python

```python
from conformance.adapter import AgentAdapter


class MonAdaptateur(AgentAdapter):
    def demarrer(self, url_mcp: str, scenario: str) -> None:
        self.agent = MonAgent(mcp_endpoint=url_mcp)  # contexte VIERGE à chaque scénario

    def envoyer(self, message: str) -> str:
        return self.agent.chat(message)  # texte utilisateur final
```

```bash
python -m conformance --agent mon_paquet.mon_module:MonAdaptateur
```

### Deux points d'attention

- **`demarrer()` doit repartir d'un contexte vierge** : aucun jeton, aucun historique,
  aucune mémoire ne doit survivre d'un scénario au suivant, sous peine de faux échecs.
- **`envoyer()` renvoie le texte utilisateur final**, pas votre trace de raisonnement
  ni un JSON interne. Le kit cherche des montants et des verbatims dans cette chaîne :
  y laisser un brouillon interne peut déclencher des échecs à tort.

## Options

```
--partenaire "Nom"        Nom porté par le rapport
--scenarios SC-01,SC-05   Sous-ensemble à jouer (défaut : les 5)
--port 8765               Port du serveur de fixtures
--sortie rapports/        Dossier du rapport
```

Le code de sortie vaut **0** si l'agent est conforme, **1** sinon : le kit s'intègre
directement dans une chaîne CI.

## Lire le résultat

Chaque contrôle porte un identifiant stable (`C05.1`…) à citer tel quel dans vos
échanges avec Acme.

- **BLOQUANT** — la conformité est refusée tant que le contrôle échoue.
- **AVERTISSEMENT** — n'empêche pas la conformité, mais doit être justifié.

Le kit écrit `rapport-conformite.json` (exploitable en CI) et
`rapport-conformite.md` (livrable à transmettre à Acme, transcriptions incluses).

## Ce que le kit ne fait pas

Il **ne contient aucune logique de détection d'Acme**. Les scénarios adverses
basculent au Nième appel de `filtrer_message`, sans que le contenu du message ne soit
jamais examiné : le kit reproduit la *cinétique* observable du serveur réel, pas ses
règles. Le moteur de compliance, le scoring de suspicion, les seuils, le DLP et le
chaînage d'audit restent privés (cf. [RFC-001 §8](../docs/RFC-001-configuration-agents-et-appel-mcp.md)).

En conséquence : **les jeux de messages sont illustratifs, non exhaustifs.** Un agent
conforme au kit n'est pas immunisé contre toute attaque, et calibrer un agent sur ces
seuls messages serait un contournement de l'esprit du contrat. Le serveur réel applique
des règles plus larges, susceptibles d'évoluer sans préavis.

Le kit ne valide pas non plus les performances réelles, la sécurité de votre
infrastructure, ni la qualité conversationnelle de votre agent.

## Support

Anomalie sur le kit lui-même, ou contrôle que vous estimez injustifié : ouvrez un
ticket en citant l'identifiant du contrôle et en joignant `rapport-conformite.json`.
