"""Résolution du code LP (landing page) — réseaux d'apport partenaires.

Le référentiel (`spec/referentiel-reseaux.json`) ne contient volontairement
aucune raison sociale ni marque partenaire : uniquement des codes, des noms de
zone géographique génériques, et des départements. Le mapping entre un réseau
déclaré par un client et son `code_reseau` est une information privée d'Acme,
hors périmètre de ce dépôt public.

Règle métier centrale : un client peut conserver le réseau régional de son
agence d'origine même après un déménagement hors de son territoire habituel.
Une estimation par département n'est donc jamais une certitude — d'où le
champ `fiabilite` renvoyé à l'appelant.
"""

import json
from pathlib import Path
from typing import Any

_REFERENTIEL_PATH = Path(__file__).resolve().parent.parent / "spec" / "referentiel-reseaux.json"
REFERENTIEL: list[dict[str, Any]] = json.loads(_REFERENTIEL_PATH.read_text(encoding="utf-8"))[
    "reseaux"
]

_COURTAGE_NATIONAL = next(r for r in REFERENTIEL if r["code_reseau"] == "900")

AVERTISSEMENT_MOBILITE = (
    "Estimation par département : un client peut conserver le réseau régional "
    "de son agence d'origine même après un déménagement hors de son territoire "
    "habituel. Confirmez le code réseau déclaré du client si une valeur exacte "
    "est requise."
)
AVERTISSEMENT_AMBIGU = (
    "Département rattaché à plusieurs réseaux régionaux limitrophes : impossible "
    "de déterminer le réseau sans confirmation du client (code réseau ou agence "
    "d'origine)."
)


def _candidats_pour_departement(departement: str) -> list[dict[str, str]]:
    return [
        {"code_reseau": r["code_reseau"], "nom": r["nom"]}
        for r in REFERENTIEL
        if isinstance(r["departements"], list) and departement in r["departements"]
    ]


def resoudre_code_lp(
    code_reseau: str | None = None, departement: str | None = None
) -> dict[str, Any] | None:
    """Renvoie {code_lp, nom_lp, fiabilite, avertissement, code_reseau_candidats}
    ou None si ni code_reseau ni departement n'est exploitable (à l'appelant de
    renvoyer REFUS_VALIDATION)."""
    if code_reseau:
        reseau = next((r for r in REFERENTIEL if r["code_reseau"] == code_reseau), None)
        if reseau is not None:
            return {
                "code_lp": reseau["code_reseau"],
                "nom_lp": reseau["nom"],
                "fiabilite": "EXACTE",
                "avertissement": None,
                "code_reseau_candidats": None,
            }
        return {
            "code_lp": _COURTAGE_NATIONAL["code_reseau"],
            "nom_lp": _COURTAGE_NATIONAL["nom"],
            "fiabilite": "INDETERMINEE",
            "avertissement": "code_reseau fourni non reconnu dans le référentiel.",
            "code_reseau_candidats": None,
        }

    if departement:
        candidats = _candidats_pour_departement(departement)
        if len(candidats) == 1:
            reseau = candidats[0]
            return {
                "code_lp": reseau["code_reseau"],
                "nom_lp": reseau["nom"],
                "fiabilite": "ESTIMEE_PAR_DEPARTEMENT",
                "avertissement": AVERTISSEMENT_MOBILITE,
                "code_reseau_candidats": None,
            }
        if len(candidats) > 1:
            return {
                "code_lp": _COURTAGE_NATIONAL["code_reseau"],
                "nom_lp": _COURTAGE_NATIONAL["nom"],
                "fiabilite": "INDETERMINEE",
                "avertissement": AVERTISSEMENT_AMBIGU,
                "code_reseau_candidats": candidats,
            }
        return {
            "code_lp": _COURTAGE_NATIONAL["code_reseau"],
            "nom_lp": _COURTAGE_NATIONAL["nom"],
            "fiabilite": "INDETERMINEE",
            "avertissement": "Aucun réseau régional associé à ce département dans le référentiel.",
            "code_reseau_candidats": None,
        }

    return None
