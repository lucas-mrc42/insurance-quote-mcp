# Cycle de vie d'une session et du jeton lead

L'agent conversationnel doit respecter cet enchaînement. Le jeton
`lead_token_ephemeral` est le fil conducteur : anonyme, éphémère (< 24 h),
à usage unique côté portail.

```
Agent (LLM)                         MCP insurance_quote
   |                                       |
   |  1. tools/call ouvrir_session ------->|
   |<--- lead_token_ephemeral + disclaimer |
   |  (afficher le disclaimer tel quel)    |
   |                                       |
   |  2. filtrer_message(token, msg) ----->|   à chaque message utilisateur
   |<--- OK | HITL_SUSPENDED               |
   |                                       |
   |  3. obtenir_tarif(token, …) --------->|   éligibilité + verbatim figé
   |<--- eligible + tarif_verbatim + magic_link
   |                                       |
   |  4. filtrer_reponse(token, texte) --->|   avant restitution à l'utilisateur
   |<--- texte_filtre                      |
   |                                       |
   |  5. Présenter le magic_link à l'utilisateur (souscription)
```

## Règles impératives côté agent

1. **Toujours** appeler `ouvrir_session` en premier et conserver le
   `lead_token_ephemeral` pour tous les appels suivants.
2. **Ne jamais** inventer un tarif, une garantie ou une remise : toute donnée
   provient des outils (`obtenir_tarif`, `obtenir_details_mrh`, `verifier_discount`).
3. Restituer le **disclaimer IA** tel quel dès le premier échange.
4. Sur `statut = HITL_SUSPENDED` : arrêter la conversation automatisée et
   présenter le message/bouton de redirection vers un conseiller.
5. Sur `statut = SERVICE_INDISPONIBLE` : restituer le message d'indisponibilité
   **tel quel**. Ne pas basculer sur les connaissances propres de l'agent
   (voir la section SLA de la RFC — c'est ce qui évite de perdre le lead).
6. Le `magic_link` est le point de sortie vers la souscription ; l'échange final
   du jeton est réalisé par le **portail** (backend-à-backend), hors périmètre agent.

## Statuts possibles

| statut | code_equivalent | Action agent |
| --- | --- | --- |
| `OK` | 200 | continuer |
| `REFUS_VALIDATION` | 422 | corriger les paramètres et réessayer |
| `HITL_SUSPENDED` | 403/422 | rediriger vers un conseiller, stopper l'automatisation |
| `REFUS` | 403 | jeton invalide/expiré → rouvrir une session |
| `SERVICE_INDISPONIBLE` | 503 | restituer le message tel quel, ne pas inventer |
