# IrrigationOS v0.9.3 Scheduling Engine

## Purpose

The Scheduling Engine answers one question:

> When should an existing irrigation plan action occur?

It consumes an immutable `IrrigationPlan` and produces an immutable
`IrrigationSchedule`. It does not recompute recommendations or planning science,
and it does not issue controller commands.

## Responsibilities

- Preserve the complete source `PlanAction` in every scheduled result.
- Place execution-ready irrigation actions into explicitly supplied permitted windows.
- Preserve runtime, target, quantity, and cycle-and-soak instructions from Planning.
- Apply deterministic inter-action spacing.
- Represent weather, freeze, municipal, or other external holds as explicit blocking constraints.
- Return typed manual-only or blocked results instead of inventing timing.
- Include algorithm, schema, policy, plan, and request provenance.

## Non-responsibilities

Scheduling does not:

- Recalculate water demand, plant stress, health, recommendations, or plan quantities.
- Modify the source irrigation plan.
- Select or control hardware.
- Open valves or communicate with Rachio.
- Infer watering windows that were not supplied.
- Override safety constraints from Planning.

## Core models

- `SchedulingWindow`
- `SchedulingPolicy`
- `SchedulingRequest`
- `ScheduledAction`
- `IrrigationSchedule`

## Schedule states

- `ready`: every plan action is scheduled.
- `partial`: at least one action remains manual-only while another action is not blocked.
- `not_schedulable`: every action is blocked.

## Deterministic placement

Actions are processed in stable plan-action order. Each execution-ready action is
placed at the earliest time at which its complete runtime and all soak intervals fit
inside a supplied scheduling window. The next action starts only after the prior
action ends and the policy's minimum inter-action spacing has elapsed.

When no window can fit an action, the action is blocked with the explicit reason
`no permitted window can fit action`.

## Safety boundary

This milestone remains hardware-independent and observation/simulation safe. The
Scheduling Engine produces proposed timing only. Command translation and equipment
control belong exclusively to the future Execution Engine.
