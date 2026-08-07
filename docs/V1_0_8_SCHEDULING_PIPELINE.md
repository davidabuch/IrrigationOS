# v1.0.8 Scheduling Pipeline Integration

## Purpose

v1.0.8 integrates the existing deterministic Scheduling domain engine into the synchronized Home Assistant pipeline. It does not create a second scheduling algorithm and does not authorize irrigation hardware control.

## Evidence flow

The synchronized flow is now:

```text
Scientific Inputs
  -> Water Requirement
  -> Plant Stress
  -> Plant Health
  -> Recommendations
  -> Planning
  -> Scheduling
```

The pipeline Scheduling adapter consumes canonical `IrrigationPlan` values and delegates schedule construction to `build_irrigation_schedule()`. The resulting `IrrigationSchedule` retains the source plan ID and each scheduled action retains its complete source `PlanAction`.

## Permitted watering windows

The current Home Assistant pipeline has no authoritative user-configured source for permitted watering windows. v1.0.8 therefore passes an empty window set to the canonical Scheduling engine rather than inventing a midnight, sunrise, or other implicit policy.

This means:

- manual-only plan actions remain manual-only and require no fabricated timing;
- blocked plan actions remain blocked;
- a genuinely ready irrigation action cannot be assigned a start time until an explicit permitted window source exists;
- no sunrise, preferred-hour, Rachio-schedule, or homeowner-policy assumption is hidden in the pipeline adapter.

## Safety boundary

Scheduling is proposal generation only. v1.0.8 does not:

- issue Rachio commands;
- create or modify controller schedules;
- start or stop watering;
- promote a manual-only action to automatic execution;
- integrate Execution or Runtime Monitoring into Home Assistant.

Execution and Runtime Monitoring remain blocked downstream. Observation and simulation remain the operating boundary.

## Determinism and degraded states

The adapter uses one stable scheduling policy identifier and preserves canonical domain statuses. Missing upstream plans remain explicit. Partial/manual-only schedules remain partial. Plans that cannot be scheduled remain blocked with stable pipeline blocker codes.
