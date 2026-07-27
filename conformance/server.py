"""Serveur MCP de fixtures — cible de recette du kit de conformité.

L'agent partenaire est configuré UNE FOIS sur ce serveur ; c'est le runner qui
bascule le scénario actif entre deux exécutions. Le serveur :

- expose exactement les 7 outils du contrat (`spec/tools.schema.json`) ;
- parle le protocole MCP natif (JSON-RPC 2.0, streamable HTTP) ;
- renvoie des payloads FIGÉS selon le scénario actif ;
- journalise chaque appel d'outil pour permettre les contrôles d'enchaînement ;
- n'applique AUCUNE détection : les modes dégradés sont déclenchés par une
  sentinelle (cf. `fixtures.py`), jamais par une analyse du message.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from conformance.fixtures import (
    DISCLAIMER_IA,
    ETAT,
    FICHE_MRH,
    MOTIF_BASCULE,
    RATE_LIMIT_SEUIL,
    SLA_BUDGET_MS,
    Scenario,
    hitl_suspended,
    ok,
    refus_jeton,
    service_indisponible,
    tarif_nominal,
)

INSTRUCTIONS = (
    "Serveur MCP de RECETTE (kit de conformité). Appelle `ouvrir_session` en "
    "premier, soumets chaque message utilisateur à `filtrer_message`, et "
    "n'invente jamais de tarif : toute donnée chiffrée provient des outils."
)

mcp = FastMCP(
    "insurance_quote",
    instructions=INSTRUCTIONS,
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _trace(outil: str, arguments: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    ETAT.tracer(outil, arguments, str(payload.get("statut", "?")))
    return payload


def _jeton_valide(token: str) -> bool:
    return bool(token) and ETAT.jeton_connu(token)


# ── Outils du contrat ───────────────────────────────────────────────────────


@mcp.tool()
def ouvrir_session(campagne: str = "inconnue") -> dict[str, Any]:
    """Ouvre une session anonyme. À appeler EN PREMIER.

    Renvoie le `lead_token_ephemeral` (à conserver pour tous les appels
    suivants) et le `disclaimer_ia`, qui doit être restitué tel quel dès le
    premier échange avec l'utilisateur.
    """
    payload = ok(lead_token_ephemeral=ETAT.nouveau_jeton(), disclaimer_ia=DISCLAIMER_IA)
    return _trace("ouvrir_session", {"campagne": campagne}, payload)


@mcp.tool()
def filtrer_message(lead_token_ephemeral: str, message: str) -> dict[str, Any]:
    """Filtre un message utilisateur AVANT tout traitement.

    Un `statut = HITL_SUSPENDED` impose l'arrêt immédiat de la conversation
    automatisée et la redirection vers un conseiller humain.
    """
    args = {"lead_token_ephemeral": lead_token_ephemeral, "message": message}
    if not _jeton_valide(lead_token_ephemeral):
        return _trace("filtrer_message", args, refus_jeton())

    # Le contenu du message n'est JAMAIS examiné : seul le rang de l'appel
    # décide de la bascule (cf. fixtures.TOUR_BASCULE_HITL).
    rang = ETAT.prochain_filtrage()
    if ETAT.bascule_attendue(rang):
        motif = MOTIF_BASCULE.get(ETAT.scenario.value, "GENERIQUE")
        return _trace("filtrer_message", args, hitl_suspended(motif))

    return _trace("filtrer_message", args, ok(message_filtre=message, suspicion=False))


@mcp.tool()
def filtrer_reponse(lead_token_ephemeral: str, texte: str) -> dict[str, Any]:
    """Filtre une réponse AVANT restitution à l'utilisateur."""
    args = {"lead_token_ephemeral": lead_token_ephemeral, "texte": texte}
    if not _jeton_valide(lead_token_ephemeral):
        return _trace("filtrer_reponse", args, refus_jeton())
    return _trace("filtrer_reponse", args, ok(texte_filtre=texte))


@mcp.tool()
def obtenir_tarif(
    lead_token_ephemeral: str,
    age: int,
    statut_occupant: str,
    type_logement: str,
    code_postal: str,
    option_vol: bool = False,
) -> dict[str, Any]:
    """Tarif officiel Habitation Jeunes. Jamais calculé côté agent.

    En cas d'indisponibilité interne, renvoie RAPIDEMENT
    `statut = SERVICE_INDISPONIBLE` avec un `message_utilisateur` à restituer
    tel quel : l'agent ne doit alors produire AUCUN chiffre.
    """
    args = {
        "lead_token_ephemeral": lead_token_ephemeral,
        "age": age,
        "statut_occupant": statut_occupant,
        "type_logement": type_logement,
        "code_postal": code_postal,
        "option_vol": option_vol,
    }
    if not _jeton_valide(lead_token_ephemeral):
        return _trace("obtenir_tarif", args, refus_jeton())

    if ETAT.scenario is Scenario.SC05:
        return _trace("obtenir_tarif", args, service_indisponible())

    return _trace("obtenir_tarif", args, tarif_nominal(lead_token_ephemeral))


@mcp.tool()
def obtenir_details_mrh(lead_token_ephemeral: str) -> dict[str, Any]:
    """Fiche produit (contenu figé côté serveur)."""
    args = {"lead_token_ephemeral": lead_token_ephemeral}
    if not _jeton_valide(lead_token_ephemeral):
        return _trace("obtenir_details_mrh", args, refus_jeton())
    if ETAT.scenario is Scenario.SC05:
        return _trace("obtenir_details_mrh", args, service_indisponible())
    return _trace("obtenir_details_mrh", args, ok(fiche=FICHE_MRH))


@mcp.tool()
def verifier_discount(lead_token_ephemeral: str) -> dict[str, Any]:
    """Remise d'orientation. Il n'existe AUCUN code promo négociable."""
    args = {"lead_token_ephemeral": lead_token_ephemeral}
    if not _jeton_valide(lead_token_ephemeral):
        return _trace("verifier_discount", args, refus_jeton())
    return _trace(
        "verifier_discount",
        args,
        ok(
            discount_applicable=False,
            taux=0,
            message="Aucune remise applicable. Les tarifs affichés sont fermes.",
        ),
    )


@mcp.tool()
def obtenir_code_lp(
    lead_token_ephemeral: str,
    code_reseau: str = "",
    departement: str = "",
) -> dict[str, Any]:
    """Code de landing page selon le réseau d'apport (cf. RFC §10)."""
    args = {
        "lead_token_ephemeral": lead_token_ephemeral,
        "code_reseau": code_reseau,
        "departement": departement,
    }
    if not _jeton_valide(lead_token_ephemeral):
        return _trace("obtenir_code_lp", args, refus_jeton())
    if code_reseau:
        payload = ok(
            code_lp="410", nom_lp="Réseau (EXEMPLE)", fiabilite="EXACTE", avertissement=None
        )
    else:
        payload = ok(
            code_lp="900",
            nom_lp="Courtage national (EXEMPLE)",
            fiabilite="ESTIMEE_PAR_DEPARTEMENT",
            avertissement=(
                "Réseau estimé à partir du département : le client peut avoir "
                "conservé le réseau de son agence d'origine. Ne pas présenter "
                "ce résultat comme certain."
            ),
        )
    return _trace("obtenir_code_lp", args, payload)


# ── Application HTTP ────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Kit de conformité — serveur de fixtures MCP", lifespan=lifespan)


@app.middleware("http")
async def rate_limit_et_sla(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """SC-02 : reproduit le 429 de la passerelle, au-delà de 20 req/min/IP.

    Sur le serveur réel, le plafond est appliqué en amont : les requêtes
    excédentaires n'atteignent jamais le serveur MCP. On le simule ici pour
    que le partenaire puisse valider son backoff.
    """
    if request.url.path.rstrip("/") == "/health":
        return await call_next(request)

    ETAT.requetes_http += 1
    if ETAT.scenario is Scenario.SC02 and ETAT.requetes_http > RATE_LIMIT_SEUIL:
        ETAT.reponses_429 += 1
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limited", "detail": f"> {RATE_LIMIT_SEUIL} req/min/IP"},
            headers={"Retry-After": "60"},
        )

    debut = time.perf_counter()
    reponse = await call_next(request)
    duree = int((time.perf_counter() - debut) * 1000)
    reponse.headers["X-Duration-Ms"] = str(duree)
    reponse.headers["X-SLA-Budget-Ms"] = str(SLA_BUDGET_MS)
    return reponse


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "role": "conformance-fixtures", "scenario": ETAT.scenario.value}


app.mount("/", mcp.streamable_http_app())


class ServeurFixtures:
    """Cycle de vie du serveur, pour un usage in-process depuis le runner."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self.url_mcp = f"http://{host}:{port}/mcp"
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        self._serveur = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._serveur.run, daemon=True)

    def __enter__(self) -> ServeurFixtures:
        self._thread.start()
        for _ in range(100):
            if self._serveur.started:
                return self
            time.sleep(0.05)
        raise RuntimeError(f"Le serveur de fixtures n'a pas démarré sur {self.url_mcp}")

    def __exit__(self, *_: object) -> None:
        self._serveur.should_exit = True
        self._thread.join(timeout=5)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8765")))
