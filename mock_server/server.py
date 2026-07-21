"""Serveur MCP **mock** — Acme Habitation Jeunes (contrat public d'intégration).

But : permettre aux partenaires (OpenAI, Anthropic, Google, Mistral) de
développer et tester leur agent contre la MÊME surface d'outils et le MÊME
protocole que le serveur réel, SANS aucune logique métier ni couche de
sécurité (celles-ci restent privées et hébergées par Acme).

Ce mock :
- expose exactement les 6 outils du contrat (`spec/tools.schema.json`) ;
- parle le protocole MCP natif (JSON-RPC 2.0, streamable HTTP) ;
- renvoie des données d'EXEMPLE clairement marquées ;
- n'applique AUCUNE authentification, AUCUN filtrage, AUCUN scoring ;
- expose l'en-tête SLA `X-SLA-Budget-Ms` à titre indicatif (cf. RFC §SLA).

Lancement :
    pip install -r requirements.txt
    python mock_server/server.py         # http://127.0.0.1:8000/mcp
"""

import os
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mock_server.example_data import (
    DISCLAIMER_IA,
    FICHE_MRH_EXEMPLE,
    MAGIC_LINK_TEMPLATE,
    exemple_tarif,
)
from mock_server.reseaux import resoudre_code_lp

SLA_BUDGET_MS = int(os.environ.get("MCP_SLA_BUDGET_MS", "2500"))

INSTRUCTIONS = (
    "Serveur MCP mock — offre Habitation Jeunes (EXEMPLE d'intégration). Appelle "
    "`ouvrir_session` en premier, soumets chaque message utilisateur à "
    "`filtrer_message`, et n'invente jamais de tarif : tout vient des outils."
)

mcp = FastMCP(
    "insurance_quote",  # snake_case : compatible tous SDK (Gemini refuse le tiret)
    instructions=INSTRUCTIONS,
    stateless_http=True,
    json_response=True,
    # Mock de dev local, sans sécurité : on n'active pas la protection DNS
    # rebinding (le serveur RÉEL, lui, l'active — cf. contrat, hors périmètre mock).
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


def _ok(**champs: Any) -> dict[str, Any]:
    return {"statut": "OK", "code_equivalent": 200, **champs}


@mcp.tool()
def ouvrir_session(reference_partenaire: str | None = None) -> dict[str, Any]:
    """Ouvre une session anonyme et renvoie le jeton éphémère + disclaimer IA.

    À appeler EN PREMIER. Le disclaimer doit être restitué tel quel à l'utilisateur.
    `reference_partenaire` (optionnel) : identifiant opaque d'attribution fourni
    par le partenaire, jamais interprété (mock : simplement renvoyé tel quel).
    """
    return _ok(
        lead_token_ephemeral=str(uuid.uuid4()),
        disclaimer_ia=DISCLAIMER_IA,
        reference_partenaire=reference_partenaire,
    )


@mcp.tool()
def filtrer_message(lead_token_ephemeral: str, message: str) -> dict[str, Any]:
    """Filtre un message utilisateur AVANT tout traitement (mock : neutre)."""
    if not lead_token_ephemeral:
        return {"statut": "REFUS", "code_equivalent": 403, "message": "jeton requis (exemple)"}
    return _ok(message_filtre=message, suspicion_score=0)


@mcp.tool()
def filtrer_reponse(lead_token_ephemeral: str, texte: str) -> dict[str, Any]:
    """Filtre une réponse AVANT restitution à l'utilisateur (mock : neutre)."""
    if not lead_token_ephemeral:
        return {"statut": "REFUS", "code_equivalent": 403, "message": "jeton requis (exemple)"}
    return _ok(texte_filtre=texte)


@mcp.tool()
def obtenir_tarif(
    lead_token_ephemeral: str,
    age: int,
    statut_occupant: str,
    type_logement: str,
    code_postal: str,
    option_vol: bool = False,
) -> dict[str, Any]:
    """Tarif Habitation Jeunes (EXEMPLE). Éligibilité fictive : locataire 18-30, T1/T2."""
    if not lead_token_ephemeral:
        return {"statut": "REFUS", "code_equivalent": 403, "message": "jeton requis (exemple)"}
    eligible = (
        statut_occupant == "LOCATAIRE" and 18 <= age <= 30 and type_logement in {"T1", "T2"}
    )
    resultat = exemple_tarif(eligible)
    contenu = _ok(**resultat)
    if eligible:
        contenu["magic_link"] = MAGIC_LINK_TEMPLATE.format(token=lead_token_ephemeral)
    return contenu


@mcp.tool()
def obtenir_details_mrh(lead_token_ephemeral: str) -> dict[str, Any]:
    """Fiche produit Habitation Jeunes (EXEMPLE)."""
    if not lead_token_ephemeral:
        return {"statut": "REFUS", "code_equivalent": 403, "message": "jeton requis (exemple)"}
    return _ok(fiche_markdown=FICHE_MRH_EXEMPLE)


@mcp.tool()
def verifier_discount(lead_token_ephemeral: str) -> dict[str, Any]:
    """Remise d'orientation (EXEMPLE) — aucun code promo."""
    if not lead_token_ephemeral:
        return {"statut": "REFUS", "code_equivalent": 403, "message": "jeton requis (exemple)"}
    return _ok(remise_applicable=False, verbatim="Aucune remise dans cet exemple.")


@mcp.tool()
def obtenir_code_lp(
    lead_token_ephemeral: str,
    code_reseau: str | None = None,
    departement: str | None = None,
) -> dict[str, Any]:
    """Code LP de routage selon le réseau d'apport du client.

    Priorité au `code_reseau` déclaré s'il est connu. À défaut, `departement`
    ne donne qu'une ESTIMATION : un client peut garder le réseau régional de
    son agence d'origine même après un déménagement (voir `fiabilite` en sortie).
    """
    if not lead_token_ephemeral:
        return {"statut": "REFUS", "code_equivalent": 403, "message": "jeton requis (exemple)"}
    if not code_reseau and not departement:
        return {
            "statut": "REFUS_VALIDATION",
            "code_equivalent": 422,
            "message": "code_reseau ou departement requis (exemple)",
        }
    resultat = resoudre_code_lp(code_reseau, departement)
    return _ok(**resultat)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="Acme Habitation Jeunes — MCP mock (contrat public)", lifespan=lifespan)


@app.middleware("http")
async def entetes_sla(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    debut = time.perf_counter()
    reponse = await call_next(request)
    duree = int((time.perf_counter() - debut) * 1000)
    reponse.headers["X-Duration-Ms"] = str(duree)
    reponse.headers["X-SLA-Budget-Ms"] = str(SLA_BUDGET_MS)  # indicatif (cf. RFC §SLA)
    return reponse


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "role": "mock", "server": "insurance_quote"}


app.mount("/", mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
