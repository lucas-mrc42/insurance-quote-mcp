"""Google — Gemini API (SDK google-genai), MCP distant.

Doc : https://ai.google.dev/gemini-api/docs/function-calling
Le support MCP est expérimental (SDK Python/JS). Le nom du serveur DOIT être en
snake_case (le tiret est interdit) : `insurance_quote`.

Deux approches selon la version du SDK :
- « managed agents » : passer un outil `mcp_server` (URL + auth) au moment de l'interaction ;
- SDK client : passer un client MCP (streamable HTTP) comme outil.
Adapter selon la version installée ; le principe (URL + Bearer + allowlist) est identique.
"""

import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# Outil MCP distant (forme « managed agents » ; cf. doc pour la signature exacte).
mcp_tool = types.Tool(
    mcp_server=types.McpServer(
        name="insurance_quote",  # snake_case obligatoire
        url="https://mcp.example.com/mcp",
        headers={"Authorization": f"Bearer {os.environ['PARTNER_MCP_TOKEN']}"},
        allowed_tools=[
            "ouvrir_session",
            "filtrer_message",
            "filtrer_reponse",
            "obtenir_tarif",
            "obtenir_details_mrh",
            "verifier_discount",
        ],
    )
)

response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents="Je cherche une assurance habitation, j'ai 22 ans.",
    config=types.GenerateContentConfig(tools=[mcp_tool]),
)
print(response.text)
