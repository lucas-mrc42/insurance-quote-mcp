"""Restitution du rapport : console, JSON et Markdown.

Le Markdown est le livrable que le partenaire renvoie à Acme : il contient les
verdicts, les contrôles échoués ET les transcriptions, ce qui permet une
contre-expertise sans rejouer la suite.
"""

from __future__ import annotations

import json
from pathlib import Path

from conformance.checks import Severite
from conformance.runner import Rapport, ResultatScenario

COCHE = "✅"
CROIX = "❌"
ALERTE = "⚠️"


def _symbole(reussi: bool, severite: Severite) -> str:
    if reussi:
        return COCHE
    return CROIX if severite is Severite.BLOQUANT else ALERTE


def afficher_console(rapport: Rapport) -> None:
    print()
    print("═" * 74)
    print(f"  Kit de conformité MCP — {rapport.partenaire}")
    print(
        f"  kit v{rapport.version_kit} · contrat v{rapport.version_contrat} · {rapport.horodatage}"
    )
    print("═" * 74)

    for resultat in rapport.resultats:
        verdict = f"{COCHE} CONFORME" if resultat.conforme else f"{CROIX} NON CONFORME"
        print(f"\n{resultat.scenario} — {resultat.titre}   [{verdict}]")
        print(f"  {resultat.objectif}")
        if resultat.trace.erreur:
            print(f"  {CROIX} Erreur d'exécution : {resultat.trace.erreur}")
        for controle in resultat.controles:
            marque = _symbole(controle.reussi, controle.severite)
            print(f"  {marque} {controle.identifiant}  {controle.libelle}")
            if not controle.reussi and controle.detail:
                print(f"       ↳ {controle.detail}")
                if controle.reference:
                    print(f"       ↳ réf. {controle.reference}")

    print()
    print("─" * 74)
    bloquants = sum(len(r.bloquants_echoues) for r in rapport.resultats)
    avertissements = sum(len(r.avertissements) for r in rapport.resultats)
    conformes = sum(1 for r in rapport.resultats if r.conforme)
    print(
        f"  {conformes}/{len(rapport.resultats)} scénario(s) conforme(s) · "
        f"{bloquants} contrôle(s) bloquant(s) en échec · {avertissements} avertissement(s)"
    )
    verdict = f"{COCHE} AGENT CONFORME" if rapport.conforme else f"{CROIX} AGENT NON CONFORME"
    print(f"  Verdict global : {verdict}")
    print("─" * 74)
    print()


def _transcription(resultat: ResultatScenario) -> list[str]:
    lignes = ["<details>", "<summary>Transcription et appels d'outils</summary>", ""]
    for i, echange in enumerate(resultat.trace.echanges, 1):
        outils = ", ".join(f"`{o}`" for o in echange.outils) or "_aucun_"
        lignes += [
            f"**Tour {i} — utilisateur**",
            "",
            f"> {echange.utilisateur}",
            "",
            f"**Tour {i} — agent** (outils appelés : {outils})",
            "",
            "> " + (echange.agent.replace("\n", "\n> ") or "_réponse vide_"),
            "",
        ]
    lignes += ["</details>", ""]
    return lignes


def en_markdown(rapport: Rapport) -> str:
    verdict = "CONFORME" if rapport.conforme else "NON CONFORME"
    lignes = [
        "# Rapport de conformité — intégration MCP `insurance_quote`",
        "",
        f"| Partenaire | **{rapport.partenaire}** |",
        "| --- | --- |",
        f"| Verdict global | **{verdict}** |",
        f"| Version du kit | {rapport.version_kit} |",
        f"| Version du contrat | {rapport.version_contrat} |",
        f"| Date d'exécution | {rapport.horodatage} |",
        "",
        "Un scénario est conforme lorsque **aucun contrôle bloquant** n'est en échec.",
        "Les avertissements n'empêchent pas la conformité mais doivent être justifiés.",
        "",
        "## Synthèse",
        "",
        "| Scénario | Intitulé | Verdict | Bloquants | Avertissements |",
        "| --- | --- | --- | --- | --- |",
    ]
    for resultat in rapport.resultats:
        marque = COCHE if resultat.conforme else CROIX
        lignes.append(
            f"| {resultat.scenario} | {resultat.titre} | {marque} | "
            f"{len(resultat.bloquants_echoues)} | {len(resultat.avertissements)} |"
        )

    lignes += ["", "## Détail par scénario", ""]
    for resultat in rapport.resultats:
        marque = COCHE if resultat.conforme else CROIX
        lignes += [
            f"### {resultat.scenario} — {resultat.titre} {marque}",
            "",
            f"_{resultat.objectif}_",
            "",
        ]
        if resultat.trace.erreur:
            lignes += [f"> {CROIX} **Erreur d'exécution :** `{resultat.trace.erreur}`", ""]
        lignes += ["| | Contrôle | Sévérité | Observation |", "| --- | --- | --- | --- |"]
        for controle in resultat.controles:
            symbole = _symbole(controle.reussi, controle.severite)
            detail = controle.detail.replace("|", "\\|") if not controle.reussi else "—"
            lignes.append(
                f"| {symbole} | **{controle.identifiant}** {controle.libelle} | "
                f"{controle.severite.value} | {detail} |"
            )
        lignes.append("")
        lignes += _transcription(resultat)

    lignes += [
        "## Ce que ce rapport n'atteste pas",
        "",
        "Le kit s'exécute contre un **serveur de fixtures** qui reproduit la surface",
        "publique du contrat, pas contre la production. Il valide le comportement de",
        "l'agent face aux statuts renvoyés ; il ne valide ni les performances réelles,",
        "ni la sécurité de l'infrastructure du partenaire, ni la qualité",
        "conversationnelle. Les jeux de messages adverses sont **illustratifs et non",
        "exhaustifs** : un agent conforme au kit n'est pas pour autant immunisé contre",
        "toute attaque. Calibrer un agent sur ces seuls messages constituerait un",
        "contournement de l'esprit du contrat.",
        "",
    ]
    return "\n".join(lignes)


def ecrire(rapport: Rapport, dossier: Path) -> tuple[Path, Path]:
    dossier.mkdir(parents=True, exist_ok=True)
    chemin_json = dossier / "rapport-conformite.json"
    chemin_md = dossier / "rapport-conformite.md"
    chemin_json.write_text(
        json.dumps(rapport.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    chemin_md.write_text(en_markdown(rapport), encoding="utf-8")
    return chemin_json, chemin_md
