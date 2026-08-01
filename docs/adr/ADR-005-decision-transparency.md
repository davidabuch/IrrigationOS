# ADR-005: Decision Transparency and Flight Recording

- **Status:** Accepted
- **Date:** 2026-08-01

## Context

Autonomous irrigation requires user trust. A binary “watered/skipped” result is insufficient for commissioning, troubleshooting, or long-term calibration.

## Decision

Every material recommendation and execution decision must preserve its evaluation context, alternatives, policy results, confidence, and human-readable explanation. Material events are written to a secret-safe Flight Recorder.

## Consequences

- The system must answer why a zone watered, skipped, changed runtime, or was deferred.
- Explanations are derived from deterministic decision artifacts rather than invented after the fact.
- Flight Recorder reliability becomes a prerequisite for Live mode.
