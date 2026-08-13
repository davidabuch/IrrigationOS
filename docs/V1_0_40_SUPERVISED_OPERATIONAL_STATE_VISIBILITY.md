# v1.0.40 — Supervised Operational State & Acceptance Visibility

## Purpose

v1.0.40 makes the bounded v1.0.39 supervised operational path observable in Home Assistant. It adds no control authority: every dispatch still uses the existing manual service, exact confirmation, accepted first-live target, current ownership and boundary review, healthy fresh confirmed observations, zero-watering-conflict gate, and 120-second maximum.

## State ownership and persistence

Each loaded IrrigationOS coordinator owns two separate supervised-operation components:

- `SupervisedOperationManager` holds transient dispatch state and safe canonical target metadata. A new coordinator always starts with no operation in progress; no command, monitor, or retry is restored after restart.
- `SupervisedOperationAcceptanceManager` stores only the latest completed structured acceptance record in Home Assistant storage. `pass`, `fail`, and `indeterminate` results survive restart.

The existing append-only files remain independent durable history:

- `/config/irrigationos_logs/supervised_operation_audit.jsonl`
- `/config/irrigationos_logs/supervised_operation_acceptance.jsonl`

Every terminal record is written to the acceptance JSONL stream and offered to the latest-result store. A storage failure fails closed to `not_available` and exposes a safe persistence error code; it never retries or resumes watering.

## Home Assistant visibility

`sensor.irrigationos_supervised_operation_acceptance` reports `not_available`, `pass`, `fail`, or `indeterminate`. Its attributes contain the latest privacy-safe structured record, criterion counts, terminal detail, schema version, and persistence error state.

`binary_sensor.irrigationos_supervised_operation_in_progress` is on only after a start was successfully dispatched and while its completion monitor awaits terminal observation. It exposes only the operation ID, canonical controller and area slots, and requested runtime. Terminal completion, failure, indeterminate timeout, or transport failure clears it. Restart reconstructs it off.

Redacted diagnostics include the same transient and latest-acceptance summaries. Provider-native controller or zone IDs, API credentials, and authorization data are never persisted or exposed by these additions.

## Safety boundary

This milestone adds observation and persistence only. It does not add autonomous watering, scheduling, target expansion, command retries, general Live authorization, command buttons, or a dependency on Home Assistant's official Rachio integration. First-live commissioning and supervised operational watering remain separate concepts and separate persistence records.
