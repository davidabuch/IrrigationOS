# IrrigationOS v0.9.5 Runtime Monitoring

Runtime Monitoring closes the deterministic IrrigationOS pipeline by comparing an immutable execution plan with immutable command outcomes and a current runtime observation.

## Responsibility

Runtime Monitoring answers: **Did execution occur as intended, and what remains unresolved?**

It may:

- classify execution as pending, in progress, completed, partial, missed, interrupted, failed, blocked, or not applicable;
- detect missing, retrying, timed-out, rejected, interrupted, and controller-offline conditions;
- preserve the complete execution, schedule, plan, recommendation, and scientific provenance chain;
- emit deterministic recovery recommendations.

It does not:

- issue controller commands;
- retry commands directly;
- modify an execution plan;
- reschedule irrigation;
- recompute recommendations or upstream science;
- call Home Assistant services or controller APIs.

## Recovery boundary

Recovery recommendations are advisory typed outputs. `retry_command`, `reschedule_remainder`, `inspect_controller`, and `manual_review` must be consumed by the appropriate upstream or operational layer. Runtime Monitoring itself performs no recovery action.
