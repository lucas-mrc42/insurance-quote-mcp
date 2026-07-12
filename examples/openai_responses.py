"""OpenAI — Responses API, outil MCP distant (type "mcp").

Doc : https://developers.openai.com/api/docs/guides/tools-connectors-mcp
Transport streamable HTTP ou SSE ; auth par en-tête (Bearer). On désactive
l'approbation humaine (`require_approval: never`) pour ne pas ajouter de latence
qui pousserait au fallback (voir SLA dans la RFC).
"""

import os

from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

response = client.responses.create(
    model="gpt-5",
    input="Je cherche une assurance habitation, j'ai 22 ans, locataire d'un T1 à Paris.",
    tools=[
        {
            "type": "mcp",
            "server_label": "insurance_quote",
            "server_url": "https://mcp.example.com/mcp",
            "authorization": os.environ["PARTNER_MCP_TOKEN"],  # Bearer émis par Acme
            "require_approval": "never",
            "allowed_tools": [
                "ouvrir_session",
                "filtrer_message",
                "filtrer_reponse",
                "obtenir_tarif",
                "obtenir_details_mrh",
                "verifier_discount",
            ],
        }
    ],
)
print(response.output_text)
