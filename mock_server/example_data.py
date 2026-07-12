"""Données d'EXEMPLE pour le serveur mock — AUCUNE valeur de production.

Tout est fictif et clairement marqué. Ne reflète ni la tarification réelle,
ni les règles d'éligibilité réelles, ni aucune logique métier de Acme.
"""

from typing import Any

DISCLAIMER_IA = (
    "Vous échangez avec un assistant IA (exemple). Les informations sont "
    "fournies à titre indicatif et ne constituent pas un devis contractuel."
)

MAGIC_LINK_TEMPLATE = "https://exemple.invalid/souscription?lead_token={token}"

# Tarifs d'EXEMPLE (fictifs) — le serveur réel renvoie des verbatims figés.
FICHE_MRH_EXEMPLE = (
    "# Habitation Jeunes (EXEMPLE)\n\n"
    "Fiche produit fictive fournie pour l'intégration. Le contenu réel est "
    "servi par le serveur de production.\n"
)


def exemple_tarif(eligible: bool) -> dict[str, Any]:
    if not eligible:
        return {
            "eligible": False,
            "cle_tarifaire": None,
            "tarif_verbatim": None,
            "motifs_exclusion": ["EXEMPLE_HORS_PERIMETRE"],
            "message": "Situation hors périmètre de l'offre (exemple).",
        }
    return {
        "eligible": True,
        "cle_tarifaire": "base",
        "tarif_verbatim": "XX,XX €/mois (EXEMPLE — valeur non contractuelle)",
        "motifs_exclusion": [],
        "message": None,
    }
