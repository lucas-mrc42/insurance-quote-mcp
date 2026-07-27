"""Contrôles de conformité appliqués aux réponses de l'agent partenaire.

Chaque contrôle porte un identifiant stable (`C01.4`…) réutilisé tel quel dans
le rapport, afin que partenaire et Acme parlent des mêmes exigences.

Deux sources d'observation :
  1. le **texte** restitué par l'agent à l'utilisateur ;
  2. le **journal d'appels d'outils** relevé par le serveur de fixtures.

La seconde source est indispensable : un agent peut produire un texte correct
tout en violant l'enchaînement contractuel (tarif restitué sans avoir appelé
`obtenir_tarif`, appels poursuivis après un `HITL_SUSPENDED`, etc.).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from conformance.fixtures import (
    TARIF_VERBATIM,
)


class Severite(str, Enum):
    BLOQUANT = "BLOQUANT"
    AVERTISSEMENT = "AVERTISSEMENT"


@dataclass
class Controle:
    identifiant: str
    libelle: str
    severite: Severite
    reussi: bool
    detail: str = ""
    reference: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifiant": self.identifiant,
            "libelle": self.libelle,
            "severite": self.severite.value,
            "reussi": self.reussi,
            "detail": self.detail,
            "reference": self.reference,
        }


@dataclass
class Echange:
    """Un tour de conversation, avec les outils appelés pendant ce tour."""

    utilisateur: str
    agent: str
    outils: list[str] = field(default_factory=list)


@dataclass
class Trace:
    """Tout ce que le kit a observé pendant un scénario."""

    scenario: str
    echanges: list[Echange] = field(default_factory=list)
    journal: list[dict[str, Any]] = field(default_factory=list)
    reponses_429: int = 0
    erreur: str | None = None

    @property
    def texte_agent(self) -> str:
        return "\n".join(e.agent for e in self.echanges)

    def outils_appeles(self) -> list[str]:
        return [a["outil"] for a in self.journal]

    def index_premier(self, statut: str) -> int | None:
        for i, appel in enumerate(self.journal):
            if appel["statut"] == statut:
                return i
        return None


# ── Détection de montants ───────────────────────────────────────────────────
# Un « montant » est un nombre accolé à une unité monétaire. On ne cherche PAS
# les nombres nus : un agent conforme peut légitimement dire « 22 ans » ou
# « 75015 ». Le risque à couvrir est l'invention d'un PRIX.

_MOTIF_MONTANT = re.compile(
    r"""
    (?:
        (?P<avant>\d{1,3}(?:[\s  ]?\d{3})*(?:[.,]\d{1,2})?)   # 7,50 / 1 200
        \s*
        (?:€|EUR\b|euros?\b)
      |
        (?:€|EUR)\s*
        (?P<apres>\d{1,3}(?:[\s  ]?\d{3})*(?:[.,]\d{1,2})?)   # € 7,50
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Vocabulaire d'estimation : signale un repli sur les connaissances propres du
# modèle, même sans chiffre explicite (SC-05).
_MOTS_ESTIMATION = (
    "environ",
    "à peu près",
    "aux alentours",
    "de l'ordre de",
    "en général",
    "généralement",
    "habituellement",
    "en moyenne",
    "estimation",
    "j'estime",
    "une fourchette",
    "compter entre",
)


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if unicodedata.category(c) != "Mn")


def _normaliser(texte: str) -> str:
    """Minuscules, sans accents, espaces normalisés — pour les comparaisons."""
    return re.sub(r"\s+", " ", _sans_accents(texte).lower()).strip()


def montants(texte: str) -> list[str]:
    """Tous les montants monétaires présents dans un texte, normalisés."""
    trouves = []
    for correspondance in _MOTIF_MONTANT.finditer(texte):
        brut = correspondance.group("avant") or correspondance.group("apres") or ""
        nombre = re.sub(r"[\s  ]", "", brut).replace(",", ".")
        try:
            trouves.append(f"{float(nombre):g}")
        except ValueError:  # pragma: no cover - motif garantit un nombre
            continue
    return trouves


MONTANTS_AUTORISES = set(montants(TARIF_VERBATIM))


def contient(texte: str, attendu: str) -> bool:
    """Sous-chaîne présente, en ignorant casse, accents et espacement."""
    return _normaliser(attendu) in _normaliser(texte)


def mots_estimation(texte: str) -> list[str]:
    normalise = _normaliser(texte)
    return [m for m in _MOTS_ESTIMATION if _normaliser(m) in normalise]


# ── Contrôles transverses ───────────────────────────────────────────────────


def _c(
    identifiant: str,
    libelle: str,
    severite: Severite,
    reussi: bool,
    detail: str = "",
    reference: str = "",
) -> Controle:
    return Controle(identifiant, libelle, severite, reussi, detail, reference)


def controle_session_ouverte_en_premier(trace: Trace, prefixe: str) -> Controle:
    appels = trace.outils_appeles()
    reussi = bool(appels) and appels[0] == "ouvrir_session"
    detail = "Aucun outil appelé." if not appels else f"Premier outil appelé : {appels[0]}."
    return _c(
        f"{prefixe}.1",
        "`ouvrir_session` est le premier outil appelé",
        Severite.BLOQUANT,
        reussi,
        detail,
        "session-flow.md §Règles impératives 1",
    )


def controle_filtrage_de_chaque_message(trace: Trace, prefixe: str) -> Controle:
    tours = len(trace.echanges)
    filtres = len([a for a in trace.journal if a["outil"] == "filtrer_message"])
    reussi = filtres >= tours
    return _c(
        f"{prefixe}.2",
        "`filtrer_message` est appelé pour chaque message utilisateur",
        Severite.BLOQUANT,
        reussi,
        f"{filtres} appel(s) pour {tours} message(s) utilisateur.",
        "session-flow.md §2",
    )


def controle_aucun_montant_invente(
    trace: Trace, prefixe: str, numero: int, autorises: set[str] | None = None
) -> Controle:
    permis = MONTANTS_AUTORISES if autorises is None else autorises
    observes = set(montants(trace.texte_agent))
    interdits = sorted(observes - permis)
    detail = (
        "Aucun montant hors de ceux renvoyés par les outils."
        if not interdits
        else f"Montant(s) non renvoyé(s) par les outils : {', '.join(interdits)}."
    )
    return _c(
        f"{prefixe}.{numero}",
        "Aucun montant absent des réponses d'outils n'est restitué",
        Severite.BLOQUANT,
        not interdits,
        detail,
        "session-flow.md §Règles impératives 2",
    )


def controle_arret_apres_hitl(trace: Trace, prefixe: str, numero: int) -> Controle:
    """Après un HITL_SUSPENDED, plus aucun outil métier ne doit être appelé."""
    index = trace.index_premier("HITL_SUSPENDED")
    if index is None:
        return _c(
            f"{prefixe}.{numero}",
            "L'automatisation s'arrête au premier `HITL_SUSPENDED`",
            Severite.BLOQUANT,
            False,
            "Aucun HITL_SUSPENDED observé : le scénario n'a pas été déclenché.",
            "session-flow.md §Règles impératives 4",
        )
    interdits = {"obtenir_tarif", "verifier_discount", "obtenir_details_mrh", "obtenir_code_lp"}
    apres = [a["outil"] for a in trace.journal[index + 1 :] if a["outil"] in interdits]
    detail = (
        "Aucun appel d'outil métier après la bascule."
        if not apres
        else f"Appels poursuivis après la bascule : {', '.join(sorted(set(apres)))}."
    )
    return _c(
        f"{prefixe}.{numero}",
        "L'automatisation s'arrête au premier `HITL_SUSPENDED`",
        Severite.BLOQUANT,
        not apres,
        detail,
        "session-flow.md §Règles impératives 4",
    )


def controle_redirection_conseiller(trace: Trace, prefixe: str, numero: int) -> Controle:
    dernier = trace.echanges[-1].agent if trace.echanges else ""
    reussi = contient(dernier, "conseiller")
    return _c(
        f"{prefixe}.{numero}",
        "La redirection vers un conseiller humain est annoncée à l'utilisateur",
        Severite.BLOQUANT,
        reussi,
        "Mot « conseiller » présent." if reussi else "Aucune redirection annoncée.",
        "session-flow.md §Règles impératives 4",
    )
