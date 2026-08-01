# IrrigationOS Vision

## Product statement

**IrrigationOS is not an irrigation timer.**

IrrigationOS is an autonomous irrigation operating system that continuously understands weather, soil, plants, hydraulics, and water demand to make safe, explainable, and efficient irrigation decisions. The irrigation controller is an execution device beneath that intelligence.

## Core distinction

> The controller waters zones. IrrigationOS manages landscapes.

A traditional controller asks whether a zone is scheduled to run. IrrigationOS asks whether the landscape served by that zone needs water, how much it needs, when that water should be applied, and why.

## Long-term outcome

A mature IrrigationOS installation should:

- discover one or more supported irrigation controllers;
- build a digital twin of the property and each landscape zone;
- combine local observations with forecast and historical weather;
- estimate soil-water reserves and plant demand;
- generate deterministic, explainable irrigation recommendations;
- schedule watering within user-defined hard boundaries;
- simulate and validate recommendations before live control;
- execute through controller-specific adapters with attribution and safety controls;
- record every material observation, decision, command, and outcome.

## Product principles

1. **Landscape first.** Zone numbers and controller brands are implementation details.
2. **Observation before control.** New capability progresses through Observation, Simulation, Shadow, and Live commissioning.
3. **Explain every decision.** Users should be able to answer why a zone watered, skipped, changed runtime, or was deferred.
4. **Controller independence.** Intelligence remains above a stable controller-adapter boundary.
5. **Conservative automation.** Missing, stale, contradictory, or low-confidence data must reduce autonomy rather than increase it.
6. **User-defined boundaries.** Users define policy, restrictions, priorities, and allowed watering windows; IrrigationOS computes the daily plan.
7. **Local reality over remote assumptions.** On-property observations outrank distant weather stations when trustworthy.
8. **Progressive disclosure.** Basic setup should be approachable while advanced calibration remains available.
9. **Auditable operation.** The Flight Recorder is a core subsystem, not a troubleshooting afterthought.
10. **No architectural shortcuts.** Early releases must preserve boundaries required by future autonomous operation.

## Success criteria

IrrigationOS succeeds when a homeowner no longer maintains fixed watering-day schedules, yet can still understand and override every recommendation and command. Water use should decrease without compromising landscape health, and trust should increase because the system is transparent, measurable, and reversible.
