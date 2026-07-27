"""Orchestration : joue les scénarios contre l'agent partenaire et évalue."""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any

from conformance.adapter import AgentAdapter
from conformance.checks import Controle, Echange, Severite, Trace
from conformance.fixtures import CONTRACT_VERSION, ETAT, KIT_VERSION, Scenario
from conformance.scenarios import CATALOGUE, DefinitionScenario


@dataclass
class ResultatScenario:
    scenario: str
    titre: str
    objectif: str
    trace: Trace
    controles: list[Controle] = field(default_factory=list)
    duree_ms: int = 0

    @property
    def bloquants_echoues(self) -> list[Controle]:
        return [c for c in self.controles if not c.reussi and c.severite is Severite.BLOQUANT]

    @property
    def avertissements(self) -> list[Controle]:
        return [c for c in self.controles if not c.reussi and c.severite is Severite.AVERTISSEMENT]

    @property
    def conforme(self) -> bool:
        return not self.bloquants_echoues and self.trace.erreur is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "titre": self.titre,
            "objectif": self.objectif,
            "conforme": self.conforme,
            "duree_ms": self.duree_ms,
            "erreur": self.trace.erreur,
            "controles": [c.to_dict() for c in self.controles],
            "echanges": [
                {"utilisateur": e.utilisateur, "agent": e.agent, "outils": e.outils}
                for e in self.trace.echanges
            ],
            "journal_outils": self.trace.journal,
            "reponses_429": self.trace.reponses_429,
        }


@dataclass
class Rapport:
    partenaire: str
    version_kit: str
    version_contrat: str
    horodatage: str
    resultats: list[ResultatScenario] = field(default_factory=list)

    @property
    def conforme(self) -> bool:
        return all(r.conforme for r in self.resultats)

    def to_dict(self) -> dict[str, Any]:
        return {
            "partenaire": self.partenaire,
            "version_kit": self.version_kit,
            "version_contrat": self.version_contrat,
            "horodatage": self.horodatage,
            "conforme": self.conforme,
            "scenarios": [r.to_dict() for r in self.resultats],
        }


def _echec_total(definition: DefinitionScenario, trace: Trace) -> list[Controle]:
    """Un scénario qui plante ne peut pas être déclaré conforme."""
    return [
        Controle(
            f"{definition.scenario.value}.ERREUR",
            "Le scénario s'est exécuté jusqu'au bout",
            Severite.BLOQUANT,
            False,
            trace.erreur or "Erreur inconnue.",
            "kit de conformité",
        )
    ]


def jouer_scenario(
    definition: DefinitionScenario, adaptateur: AgentAdapter, url_mcp: str
) -> ResultatScenario:
    debut = time.perf_counter()
    ETAT.demarrer(definition.scenario)
    trace = Trace(scenario=definition.scenario.value)

    try:
        adaptateur.demarrer(url_mcp, definition.scenario.value)
        for message in definition.messages:
            deja_vus = len(ETAT.appels())
            reponse = adaptateur.envoyer(message)
            if not isinstance(reponse, str):
                raise TypeError(
                    f"envoyer() doit renvoyer une chaîne, reçu {type(reponse).__name__}"
                )
            outils = [a.outil for a in ETAT.appels()[deja_vus:]]
            trace.echanges.append(Echange(message, reponse, outils))
    except Exception as erreur:  # noqa: BLE001 — on veut un rapport, pas un crash
        trace.erreur = f"{type(erreur).__name__}: {erreur}"
        trace.journal = [a.to_dict() for a in ETAT.appels()]
        trace.reponses_429 = ETAT.reponses_429
        return ResultatScenario(
            definition.scenario.value,
            definition.titre,
            definition.objectif,
            trace,
            _echec_total(definition, trace),
            int((time.perf_counter() - debut) * 1000),
        )

    trace.journal = [a.to_dict() for a in ETAT.appels()]
    trace.reponses_429 = ETAT.reponses_429

    try:
        controles = definition.evaluer(trace)
    except Exception:  # noqa: BLE001
        trace.erreur = "Évaluation impossible :\n" + traceback.format_exc(limit=3)
        controles = _echec_total(definition, trace)

    return ResultatScenario(
        definition.scenario.value,
        definition.titre,
        definition.objectif,
        trace,
        controles,
        int((time.perf_counter() - debut) * 1000),
    )


def executer(
    adaptateur: AgentAdapter,
    url_mcp: str,
    partenaire: str,
    scenarios: list[str] | None = None,
) -> Rapport:
    retenus = [d for d in CATALOGUE if scenarios is None or d.scenario.value in scenarios]
    if not retenus:
        connus = ", ".join(s.value for s in Scenario)
        raise ValueError(f"Aucun scénario retenu. Valeurs possibles : {connus}")

    rapport = Rapport(
        partenaire=partenaire,
        version_kit=KIT_VERSION,
        version_contrat=CONTRACT_VERSION,
        horodatage=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    )
    for definition in retenus:
        rapport.resultats.append(jouer_scenario(definition, adaptateur, url_mcp))
    adaptateur.terminer()
    return rapport
