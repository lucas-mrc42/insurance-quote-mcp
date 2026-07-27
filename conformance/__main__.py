"""CLI du kit de conformité.

    python -m conformance --agent-url http://localhost:9000/chat --partenaire "ACME LLM"
    python -m conformance --agent mon_module:MonAdaptateur --scenarios SC-01,SC-05
    python -m conformance --demo conforme        # auto-test du kit

Code de sortie : 0 si l'agent est conforme, 1 sinon (exploitable en CI).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from conformance.adapter import AgentAdapter, HttpAgentAdapter, charger_adaptateur
from conformance.fixtures import KIT_VERSION
from conformance.report import afficher_console, ecrire
from conformance.runner import executer
from conformance.server import ServeurFixtures


def _analyser(argv: list[str] | None = None) -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(
        prog="python -m conformance",
        description="Kit de conformité MCP — offre Habitation Jeunes (Acme).",
    )
    cible = analyseur.add_mutually_exclusive_group(required=True)
    cible.add_argument("--agent-url", help="Endpoint HTTP de votre agent (POST JSON).")
    cible.add_argument("--agent", help="Adaptateur Python, sous la forme « module:Classe ».")
    cible.add_argument(
        "--demo",
        choices=("conforme", "fautif"),
        help="Auto-test du kit avec un agent de référence (aucun agent partenaire requis).",
    )
    analyseur.add_argument("--partenaire", default="Partenaire non nommé")
    analyseur.add_argument("--host", default="127.0.0.1")
    analyseur.add_argument("--port", type=int, default=8765)
    analyseur.add_argument(
        "--scenarios",
        help="Liste séparée par des virgules (défaut : tous). Ex. : SC-01,SC-05",
    )
    analyseur.add_argument(
        "--sortie", type=Path, default=Path("rapports"), help="Dossier du rapport."
    )
    analyseur.add_argument("--version", action="version", version=f"kit {KIT_VERSION}")
    return analyseur.parse_args(argv)


def _construire_adaptateur(arguments: argparse.Namespace) -> AgentAdapter:
    if arguments.agent_url:
        return HttpAgentAdapter(arguments.agent_url)
    if arguments.agent:
        return charger_adaptateur(arguments.agent)

    from conformance.reference_agents import AgentConforme, AgentFautif

    return AgentConforme() if arguments.demo == "conforme" else AgentFautif()


def main(argv: list[str] | None = None) -> int:
    arguments = _analyser(argv)
    scenarios = (
        [s.strip().upper() for s in arguments.scenarios.split(",")] if arguments.scenarios else None
    )
    adaptateur = _construire_adaptateur(arguments)

    with ServeurFixtures(arguments.host, arguments.port) as serveur:
        print(f"Serveur de fixtures MCP : {serveur.url_mcp}")
        rapport = executer(adaptateur, serveur.url_mcp, arguments.partenaire, scenarios)

    afficher_console(rapport)
    chemin_json, chemin_md = ecrire(rapport, arguments.sortie)
    print(f"Rapport JSON     : {chemin_json}")
    print(f"Rapport Markdown : {chemin_md}\n")
    return 0 if rapport.conforme else 1


if __name__ == "__main__":
    sys.exit(main())
