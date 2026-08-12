# v1.0.35 — Supervised First-Live Operator Interface

This milestone exposes the v1.0.34 one-shot executor only through Home Assistant's interactive options flow.

Safety boundary:
- one currently observed Rachio controller/zone
- runtime limited to 1–120 seconds
- exact typed operator confirmation
- fresh coordinator refresh before execution
- v1.0.34 commissioning/preflight/audit rules remain authoritative
- approval and supervised window are ephemeral and closed after every attempt
- no irrigation command service
- no irrigation command button entity
- no scheduler, automation, or coordinator dispatch path
- no automatic retry after ambiguous transport outcome
