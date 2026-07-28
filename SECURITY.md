# Security policy

YuanQi Agent processes medical-domain knowledge and uses a layered trust model.
Please do not open public issues containing credentials, access tokens, patient information, medical records, screenshots with sensitive data, or exploit details.

## Reporting a vulnerability

Report security issues privately to the repository owner. Include a concise description, affected component, reproduction steps, and the potential impact. Do not include real patient data or active credentials.

The following should never be committed:

- `.env` files, JWTs, passwords, API keys, or database dumps
- LangGraph checkpoints and local SQLite state
- Neo4j, MySQL, Redis, or Qdrant volumes
- patient records, prescriptions, uploaded reports, or other clinical data

Development-only authentication endpoints must remain disabled outside the `dev` Spring profile. Production secrets must be provided through a secret manager or deployment environment, never through Git.
