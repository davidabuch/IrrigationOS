# IrrigationOS v0.9.2 — Planning Engine

## Purpose

Planning answers one question:

> What exactly should be executed?

It consumes an immutable `RecommendationAssessment` and creates an immutable, machine-readable `IrrigationPlan`. Planning does not schedule clock times, issue controller commands, or recompute upstream science.

## Contracts

- `PlanningDirective` supplies an explicit target and, where available, quantity, runtime, and cycle-and-soak details.
- `PlanningRequest` combines the accepted recommendation assessment, directives, policy, and timestamp.
- `PlanAction` preserves the source recommendation, supporting assessment identifiers, preconditions, safety constraints, and blocking reasons.
- `IrrigationPlan` contains ordered actions, typed status, unresolved issues, policy provenance, algorithm version, and schema version.

## Conservative behavior

Planning never invents a target, irrigation quantity, runtime, or cycle-and-soak instruction. Missing information is represented as a blocking reason and unresolved issue.

Current v0.9.1 recommendations include `no_automatic_execution`. Planning preserves that safety constraint. Even a quantitatively complete irrigation action therefore remains `manual_only` until a later, explicitly approved recommendation policy authorizes automatic execution.

## Status semantics

- `ready`: every action is complete and authorized for execution.
- `partial`: at least one action is usable, but one or more actions are manual-only or blocked.
- `not_executable`: every action is blocked.

## Explicit boundaries

The Planning Engine:

- does not select clock times;
- does not order work by a watering window;
- does not call Home Assistant services or controller adapters;
- does not alter recommendations;
- does not calculate plant health, stress, or water requirement;
- does not silently bypass recommendation safety flags.
