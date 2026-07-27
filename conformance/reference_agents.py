"""Agents de référence — servent à l'auto-test du kit, pas à la recette.

`AgentConforme` illustre le comportement attendu par le contrat : c'est aussi
la meilleure documentation exécutable de l'enchaînement d'appels. `AgentFautif`
commet volontairement les fautes que le kit doit détecter — il garantit que la
suite n'est pas complaisante (un kit qui ne recale personne ne vaut rien).

Aucun LLM ici : ce sont des automates scriptés. Le kit, lui, est agnostique.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from conformance.adapter import AgentAdapter
from conformance.fixtures import MESSAGE_REDIRECTION_HITL

ENTETES_MCP = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
CODE_POSTAL = re.compile(r"\b\d{5}\b")


class ErreurThrottling(Exception):
    """La passerelle a renvoyé un HTTP 429."""


class ClientMCP:
    """Client JSON-RPC minimal, suffisant pour piloter le serveur de fixtures."""

    def __init__(self, url_mcp: str, timeout_s: float = 10.0) -> None:
        # trust_env=False : le serveur de fixtures est en loopback. Sans cela,
        # un HTTP_PROXY/ALL_PROXY d'entreprise détournerait l'appel — panne
        # classique et déroutante en environnement corporate.
        self._client = httpx.Client(
            base_url=url_mcp.removesuffix("/mcp"), timeout=timeout_s, trust_env=False
        )
        self._id = 0
        self.initialise = False

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._id += 1
        reponse = self._client.post(
            "/mcp",
            headers=ENTETES_MCP,
            json={"jsonrpc": "2.0", "id": self._id, "method": method, "params": params},
        )
        if reponse.status_code == 429:
            raise ErreurThrottling(reponse.headers.get("Retry-After", "60"))
        reponse.raise_for_status()
        corps: dict[str, Any] = reponse.json()
        return corps

    def initialiser(self) -> None:
        if self.initialise:
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "conformance-reference-agent", "version": "1.0"},
            },
        )
        self.initialise = True

    def appeler(self, nom: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.initialiser()
        corps = self._rpc("tools/call", {"name": nom, "arguments": arguments})
        resultat = corps.get("result", {})
        structure = resultat.get("structuredContent")
        if isinstance(structure, dict):
            # FastMCP encapsule les retours non-objets sous la clé "result".
            return structure.get("result", structure) if set(structure) == {"result"} else structure
        contenu = resultat.get("content") or []
        if contenu and isinstance(contenu[0], dict):
            charge: dict[str, Any] = json.loads(contenu[0].get("text", "{}"))
            return charge
        return {}

    def fermer(self) -> None:
        self._client.close()


class AgentConforme(AgentAdapter):
    """Implémentation de référence respectant l'intégralité du contrat."""

    def demarrer(self, url_mcp: str, scenario: str) -> None:
        self.client = ClientMCP(url_mcp)
        self.token = ""
        self.disclaimer = ""
        self.suspendu = False
        self.throttle = False
        self.tarif: dict[str, Any] | None = None

    def terminer(self) -> None:
        client = getattr(self, "client", None)
        if client is not None:
            client.fermer()

    # ── Enchaînement contractuel ────────────────────────────────────────────
    def envoyer(self, message: str) -> str:
        # 4. HITL : l'automatisation est close, plus aucun appel d'outil.
        if self.suspendu:
            return MESSAGE_REDIRECTION_HITL
        # Backoff : après un 429, on cesse d'appeler et on temporise.
        if self.throttle:
            return (
                "Nos services sont très sollicités actuellement. "
                "Merci de patienter un instant avant de renvoyer votre demande."
            )

        try:
            return self._traiter(message)
        except ErreurThrottling as erreur:
            self.throttle = True
            return (
                "Nos services sont temporairement saturés "
                f"(nouvelle tentative possible dans {erreur} secondes). "
                "Merci de réessayer dans un instant."
            )

    def _traiter(self, message: str) -> str:
        prefixe = ""

        # 1. `ouvrir_session` en premier ; disclaimer restitué tel quel.
        if not self.token:
            session = self.client.appeler("ouvrir_session", {"campagne": "conformance"})
            self.token = str(session.get("lead_token_ephemeral", ""))
            self.disclaimer = str(session.get("disclaimer_ia", ""))
            prefixe = self.disclaimer + "\n\n"

        # 2. Chaque message utilisateur passe par `filtrer_message`.
        filtre = self.client.appeler(
            "filtrer_message", {"lead_token_ephemeral": self.token, "message": message}
        )
        if filtre.get("statut") == "HITL_SUSPENDED":
            self.suspendu = True
            return prefixe + str(filtre.get("message_utilisateur", MESSAGE_REDIRECTION_HITL))

        # 3. Tarification : uniquement quand les éléments nécessaires sont réunis.
        if self.tarif is None and CODE_POSTAL.search(message):
            self.tarif = self.client.appeler(
                "obtenir_tarif",
                {
                    "lead_token_ephemeral": self.token,
                    "age": 22,
                    "statut_occupant": "LOCATAIRE",
                    "type_logement": "T1",
                    "code_postal": CODE_POSTAL.search(message).group(0),  # type: ignore[union-attr]
                    "option_vol": False,
                },
            )

        return prefixe + self._rediger(message)

    def _rediger(self, message: str) -> str:
        # 5. SERVICE_INDISPONIBLE : verbatim strict, aucun chiffre, même si
        #    l'utilisateur insiste (c'est tout l'enjeu de SC-05).
        if self.tarif and self.tarif.get("statut") == "SERVICE_INDISPONIBLE":
            return str(self.tarif.get("message_utilisateur", ""))

        if self.tarif and self.tarif.get("statut") == "OK":
            verbatim = self.tarif.get("tarif_verbatim", "")
            lien = self.tarif.get("magic_link", "")
            if "souscri" in message.lower() or "comment" in message.lower():
                return f"Pour souscrire, laissez-vous guider depuis ce lien sécurisé :\n{lien}"
            return (
                f"Pour votre situation, le tarif est de {verbatim}.\n"
                f"Vous pouvez poursuivre la souscription ici : {lien}"
            )

        return (
            "Je peux vous renseigner sur notre offre Habitation Jeunes. "
            "Pouvez-vous me préciser votre âge, votre statut d'occupant, "
            "le type de logement et votre code postal ?"
        )


class AgentFautif(AgentConforme):
    """Agent volontairement non conforme — valide le pouvoir de détection du kit.

    Fautes injectées : disclaimer omis, hallucination tarifaire en situation
    d'indisponibilité, poursuite de l'automatisation après bascule HITL, et
    promesse commerciale sous pression émotionnelle.
    """

    def envoyer(self, message: str) -> str:
        try:
            reponse = self._traiter(message)
        except ErreurThrottling:
            # Faute : invente un tarif plutôt que d'absorber le throttling.
            return "Nos serveurs répondent mal, mais comptez environ 8 €/mois."
        # Faute : ignore la suspension et reste en pilotage automatique.
        self.suspendu = False
        return reponse

    def _traiter(self, message: str) -> str:
        prefixe = ""
        if not self.token:
            session = self.client.appeler("ouvrir_session", {"campagne": "conformance"})
            self.token = str(session.get("lead_token_ephemeral", ""))
            self.disclaimer = str(session.get("disclaimer_ia", ""))
            # Faute : le disclaimer IA n'est jamais restitué à l'utilisateur.

        filtre = self.client.appeler(
            "filtrer_message", {"lead_token_ephemeral": self.token, "message": message}
        )
        if filtre.get("statut") == "HITL_SUSPENDED":
            # Faute majeure : au lieu de clore, l'agent part chercher une remise.
            remise = self.client.appeler("verifier_discount", {"lead_token_ephemeral": self.token})
            return (
                "Un instant, je regarde ce que je peux faire pour vous… "
                f"{remise.get('message', '')} Cela dit, je peux vous faire un geste commercial."
            )

        if self.tarif is None and CODE_POSTAL.search(message):
            self.tarif = self.client.appeler(
                "obtenir_tarif",
                {
                    "lead_token_ephemeral": self.token,
                    "age": 22,
                    "statut_occupant": "LOCATAIRE",
                    "type_logement": "T1",
                    "code_postal": CODE_POSTAL.search(message).group(0),  # type: ignore[union-attr]
                    "option_vol": False,
                },
            )

        return prefixe + self._rediger(message)

    def _rediger(self, message: str) -> str:
        if self.tarif and self.tarif.get("statut") == "SERVICE_INDISPONIBLE":
            # Faute majeure : hallucination d'un tarif malgré la consigne stricte.
            return (
                "Notre outil de tarification ne répond pas, mais d'après nos grilles "
                "habituelles, comptez environ 8,50 €/mois pour un studio à Paris."
            )
        if "remise" in message.lower() or "réduction" in message.lower():
            # Faute : promesse commerciale hors cadre.
            return "Je comprends votre situation, je peux vous faire un geste commercial de 10 %."
        return super()._rediger(message)
