"""Point de branchement du kit sur l'agent du partenaire.

Le kit ne sait rien de votre architecture. Il a besoin d'une seule chose :
pouvoir envoyer un message utilisateur et récupérer le texte que votre agent
aurait affiché à l'écran.

Deux façons de brancher votre agent :

1. **Adaptateur HTTP** (le plus simple) — exposez un endpoint qui reçoit
   `{"session_id": "...", "message": "..."}` et répond `{"reply": "..."}`,
   puis lancez :

       python -m conformance --agent-url http://localhost:9000/chat

2. **Adaptateur Python** — sous-classez `AgentAdapter` dans votre propre
   module, puis lancez :

       python -m conformance --agent mon_paquet.mon_module:MonAdaptateur

Dans les deux cas, votre agent doit être configuré pour appeler le serveur MCP
de fixtures dont l'URL vous est communiquée par `demarrer()` (par défaut
http://127.0.0.1:8765/mcp).
"""

from __future__ import annotations

import importlib
import uuid
from abc import ABC, abstractmethod
from typing import Any

import httpx


class AgentAdapter(ABC):
    """Interface minimale à implémenter côté partenaire."""

    @abstractmethod
    def demarrer(self, url_mcp: str, scenario: str) -> None:
        """Ouvre une conversation neuve.

        `url_mcp` est l'endpoint MCP à utiliser pour CETTE conversation.
        L'agent doit repartir d'un contexte vierge : aucun état, aucun jeton et
        aucun historique ne doit subsister d'un scénario à l'autre.
        """

    @abstractmethod
    def envoyer(self, message: str) -> str:
        """Traite un message utilisateur et renvoie le texte affiché à l'écran.

        Renvoyez le texte **tel que l'utilisateur le verrait**, sans balisage
        interne ni trace de raisonnement.
        """

    def terminer(self) -> None:  # noqa: B027 — hook facultatif, volontairement non abstrait
        """Libère les ressources éventuelles.

        Implémentation par défaut : ne fait rien. À redéfinir si votre agent
        détient des connexions, un pool ou un processus à refermer.
        """


class HttpAgentAdapter(AgentAdapter):
    """Adaptateur générique pour un agent exposé derrière un endpoint HTTP.

    Contrat attendu :
        POST <url>  {"session_id", "message", "mcp_url", "scenario"}
        200         {"reply": "texte affiché à l'utilisateur"}

    Les clés alternatives `response`, `text`, `output` et `content` sont
    acceptées en lecture, pour éviter un aller-retour d'intégration.
    """

    def __init__(self, url: str, timeout_s: float = 60.0, entetes: dict[str, str] | None = None):
        self.url = url
        # Un agent servi en local ne doit pas transiter par le proxy d'entreprise
        # (HTTP_PROXY / ALL_PROXY) : cause fréquente d'échecs incompréhensibles.
        loopback = any(h in url for h in ("127.0.0.1", "localhost", "[::1]", "0.0.0.0"))
        self._client = httpx.Client(
            timeout=timeout_s, headers=entetes or {}, trust_env=not loopback
        )
        self._session = ""
        self._url_mcp = ""
        self._scenario = ""

    def demarrer(self, url_mcp: str, scenario: str) -> None:
        self._session = str(uuid.uuid4())
        self._url_mcp = url_mcp
        self._scenario = scenario

    def envoyer(self, message: str) -> str:
        reponse = self._client.post(
            self.url,
            json={
                "session_id": self._session,
                "message": message,
                "mcp_url": self._url_mcp,
                "scenario": self._scenario,
            },
        )
        reponse.raise_for_status()
        corps: Any = reponse.json()
        if isinstance(corps, str):
            return corps
        for cle in ("reply", "response", "text", "output", "content", "message"):
            valeur = corps.get(cle)
            if isinstance(valeur, str):
                return valeur
        raise ValueError(
            "Réponse de l'agent illisible : aucune des clés reply/response/text/"
            f"output/content/message n'est une chaîne. Reçu : {list(corps)[:8]}"
        )

    def terminer(self) -> None:
        self._client.close()


def charger_adaptateur(reference: str) -> AgentAdapter:
    """Instancie un adaptateur depuis une référence « module:Classe »."""
    if ":" not in reference:
        raise ValueError(f"Référence attendue sous la forme « module:Classe », reçu : {reference}")
    nom_module, nom_classe = reference.split(":", 1)
    module = importlib.import_module(nom_module)
    classe = getattr(module, nom_classe)
    instance = classe()
    if not isinstance(instance, AgentAdapter):
        raise TypeError(f"{reference} n'hérite pas de conformance.adapter.AgentAdapter")
    return instance
