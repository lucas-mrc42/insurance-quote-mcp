"""Kit de conformité — intégration MCP `insurance_quote` (Acme Assurances).

Le kit vérifie que l'agent conversationnel d'un partenaire respecte le contrat
d'intégration sur les 5 scénarios de recette SC-01 à SC-05.

Il s'exécute contre un serveur de fixtures embarqué : aucune connexion à la
production, aucune donnée réelle, aucune logique métier ou de détection d'Acme.
"""

from conformance.fixtures import CONTRACT_VERSION, KIT_VERSION, Scenario

__all__ = ["CONTRACT_VERSION", "KIT_VERSION", "Scenario"]
