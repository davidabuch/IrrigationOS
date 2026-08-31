# v1.0.65 — Baseline Water Budget & Cadence Foundation

## Boundary

This release extends the existing quantitative water balance and production recommendation. It
does not add a second demand or rainfall engine, calculate runtime, schedule watering, call a
controller, or authorize execution. `estimated_runtime_seconds` remains `None`.

## Accounting and cadence

For each exact non-overlapping interval:

```text
closing deficit = max(
  0,
  opening carried deficit
  + reference ET₀ × admitted plant factor
  - effective observed precipitation
  - independently quantified irrigation depth,
)
```

Current scientific state is one bounded record per production target. Its `accounted_through`
boundary advances only to the end of a completed canonical hourly weather interval. Coordinator
clock time does not create evidence, and repeated five-minute refreshes at the same hourly
boundary perform no Store write. The next consumed interval starts at the prior boundary; gaps,
overlaps, and replay fail closed. Every timestamp in an advancing historical interval must form
an exact contiguous hourly sequence. A missing first, internal, or final hour leaves both the
durable boundary and prior deficit unchanged; later arrival of the missing observation permits
the complete interval to be admitted without interpolation or double counting.

Forecast deferral/reconciliation remains a separate event stream. Every unresolved deferral is
retained; resolved events are used only as a bounded audit tail. Because compaction retains the
newest individual resolved events, that audit-only tail may begin with a reconciliation whose
older matching deferral was compacted. Runtime reconciliation does not require complete resolved
pairs, while unresolved deferrals are never compacted. Schema-1 v1.0.64 forecast events migrate
losslessly without fabricating a numeric opening or ordinary checkpoint. All targets and forecast
changes found in one refresh are saved atomically before becoming authoritative in memory.

Cadence is not a calendar interval. Deficit accumulates faster under higher ET and more slowly
under lower ET. Effective rain reduces the accumulated deficit. Irrigation becomes scientifically
indicated only when the deficit reaches the root-zone allowable-depletion trigger.

## Demand-factor precedence

The precedence is:

1. admitted curated plant-factor evidence;
2. bounded generic canonical landscape-class policy;
3. insufficient evidence.

Generic class ranges are intentionally lower-confidence planning evidence. They do not claim a
known species. Unknown and custom classes remain unresolved.

## Root-zone reservoir and trigger

The policy computes:

```text
root-zone available water depth
  = soil available-water capacity per metre × explicit root depth

irrigation trigger deficit
  = root-zone available water depth × allowable depletion fraction
```

Soil capacities are bounded generic texture-class policy ranges, not site measurements. Unknown
or custom soil and missing root depth fail closed. Establishment is represented through the
canonical stage: newly planted and establishing vegetation use smaller allowable-depletion
fractions than established equivalents.

Policy tables are centralized in `quantitative_water_balance/policy.py` and versioned as baseline
water-budget policy `1.0.0`. The encompassing water-balance policy is `2.0.0` and model schema is
`2`.

## Rain and forecast

Observed rain enters historical accounting only through the existing effective-precipitation
boundary. Production uses the explicit conservative generic retention fraction `0.65` with
confidence `0.60`; zero rain still needs no transformation. This policy is not a claim that every
site retains exactly 65 percent—site-specific evidence can replace it later.

Forecast rain remains provisional. It can defer an otherwise indicated need under the existing
forecast policy, but it never enters historical balance until observed and reconciled.

## Bootstrap

Opening state is explicit:

- `unknown`: no defensible numeric opening exists;
- `reconstructed`: observed actual water proved a deterministic opening;
- `durable_carry_forward`: the bounded per-target state supplies the opening;
- `invalidated_by_unquantified_irrigation`: watering occurred without admissible depth.

A fresh installation is `unknown`, not zero and not assumed field capacity. Unknown opening
withholds numeric deficit and target depth. Production can leave unknown after a provably
saturating actual-water interval: the lower bound of effective observed rain plus independently
quantified irrigation must meet or exceed the upper root-zone reservoir plus upper interval
demand. Forecast water and unquantified runtime never qualify. The zero closing deficit is
recorded as reconstructed; the next completed interval becomes ordinary durable carry.

An unquantified completed watering session invalidates numeric continuity at the exact completed
weather boundary. Its identity and reason remain in current state, no water credit is awarded,
and advancing the boundary prevents the same session from poisoning every later interval. A
later provably saturating observed interval can reconstruct the balance. This is the truthful
shadow-mode behavior while native Rachio schedules remain authoritative before v1.0.66.

## Replenishment policy

Below the trigger, no irrigation depth is recommended. At or above the trigger, the target is full
restoration toward zero modeled deficit, capped by both current deficit and root-zone reservoir:

```text
target replenishment depth = min(current deficit, root-zone available water)
```

Ranges remain ranges. If deficit and trigger ranges overlap without proving either side, the
decision is withheld as uncertain. Runtime conversion, distribution loss, and cycle-and-soak are
deferred to a later delivery milestone.

Slope is not a plant-demand multiplier in this release. It belongs in later site-specific
effective-rain/runoff policy and v1.0.66 delivery planning, including application-rate limits and
cycle-and-soak. The centralized generic `0.65` effective-rain fraction remains replaceable when
soil, slope, intensity, and site evidence become admissible.

## Shadow output and safety

Per-zone water-balance output now contains factor source, opening state, deficit, root-zone
reservoir, allowable depletion, trigger depth/state, irrigation indication, replenishment depth,
rain evidence, confidence, completeness, reasons, blockers, and validity times. Existing sensors,
diagnostics, and shadow records carry this deterministic output.

Every result remains `execution_authorized = false`. Manual watering, guided observation,
supervised operation, first-live delivery, delayed stop confirmation, valves, scheduling, and
quantitative irrigation-credit admission are unchanged.
