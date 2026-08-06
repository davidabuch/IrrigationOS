# IrrigationOS v0.9.4 Execution Engine

## Purpose

The Execution Engine answers one question:

> What controller commands would be required to carry out an immutable irrigation schedule?

It does not communicate with Home Assistant, Rachio, valves, or any other hardware transport.

## Boundary

The engine consumes an `IrrigationSchedule` and produces an immutable `ExecutionPlan` containing deterministic controller commands. It never recalculates observations, water requirements, stress, health, recommendations, plans, or schedules.

## Capabilities

- Deterministic start and stop command generation for every scheduled cycle
- Stable command identifiers and idempotency keys
- Explicit IrrigationOS command attribution
- Simulation-only safety blocking
- Acknowledgement timeout, retry-count, and retry-delay policy modeling
- Typed acknowledgement, retry, timeout, and rejection results
- Complete schedule and scheduled-action provenance

## Safety

v0.9.4 contains no controller adapter invocation and no Home Assistant service calls. A safety block prevents command generation. Command outcomes are immutable models only; they do not trigger retries or hardware writes.

## Downstream contract

Runtime Monitoring may consume execution plans and command results to determine whether expected work occurred. It must not alter the source schedule or recompute upstream science.
