# Security policy

## Supported versions

IrrigationOS is pre-release software. Only the latest commit on `main` is supported during development.

## Reporting a vulnerability

Open a private GitHub security advisory for the repository owner. Do not place Rachio API keys, exact home coordinates, or unredacted diagnostics in a public issue.

## Credential handling requirements

- Rachio API keys must remain in Home Assistant config-entry storage.
- Credentials must never appear in logs, diagnostics, Flight Recorder records, entity attributes, or exceptions.
- Diagnostics must redact identifiers that can expose a person, controller, zone, or property.
