"""Anthropic — Messages API, connecteur MCP distant.

Doc : https://platform.claude.com/docs/en/agents-and-tools/mcp-connector
Le MCP est passé via `mcp_servers` ; l'auth est un jeton porteur (`authorization_token`).
On restreint explicitement les outils autorisés (allowlist).
"""

import os

import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

response = client.messages.create(
    model="claude-opus-4-8",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Je cherche une assurance habitation, j'ai 22 ans."}],
    mcp_servers=[
        {
            "type": "url",
            "url": "https://mcp.example.com/mcp",  # endpoint réel Acme (HTTPS, cert valide)
            "name": "insurance_quote",  # snake_case
            "authorization_token": os.environ["PARTNER_MCP_TOKEN"],  # Bearer émis par Acme
            "tool_configuration": {
                "enabled": True,
                "allowed_tools": [
                    "ouvrir_session",
                    "filtrer_message",
                    "filtrer_reponse",
                    "obtenir_tarif",
                    "obtenir_details_mrh",
                    "verifier_discount",
                ],
            },
        }
    ],
    extra_headers={"anthropic-beta": "mcp-client-2025-11-15"},  # cf. doc pour la version courante
)
print(response)
