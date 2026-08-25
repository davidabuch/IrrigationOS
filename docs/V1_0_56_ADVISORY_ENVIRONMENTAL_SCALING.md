# v1.0.56 — Advisory Environmental Scaling for User-Calibrated Baselines

v1.0.56 adds a pure advisory assessment for baseline-mode commissioned zones.

## Scientific model

The baseline stores runtime and its descriptive temperature/dry-condition context.
An optional immutable environmental reference adds measured or reviewed ET₀, period,
timestamp, source, and confidence. Scaling is calculated only when v1.0.55 admits the
baseline and matching fresh normalized current ET₀ evidence is complete:

`raw demand ratio = max(current ET₀ - effective observed rain, 0) / reference ET₀`

The policy factor is the raw ratio bounded to 0.5–1.5. The advisory equivalent runtime
is baseline runtime multiplied by that bounded factor. The bounds limit the influence
of a single assessment and are not plant or hydraulic facts. No temperature ratio or
per-degree multiplier is used.

## Rain and forecast

Exactly zero observed rain needs no site transformation. Positive rain receives credit
only through an explicit canonical effective-precipitation policy. A qualifying forecast
uses the existing minimum amount, freshness, horizon, quality, and confidence policy to
produce `forecast_hold`; it does not reduce historical observed demand.

## Fail-closed behavior

Legacy baselines and newly entered baselines without reference ET₀ remain admissible
commissioning evidence but scaling is withheld with `reference_et0_unavailable`.
Missing, incomplete, stale, or below-confidence weather evidence also withholds output.
Plant identity and plant-factor evidence are not required or multiplied into this path.

## Home Assistant and lifecycle

The coordinator recomputes assessments after canonical weather refresh. Current results
are transient, bounded review/diagnostic evidence. They are never restored as authority,
create no task or listener, and trigger no extra network request. The commissioning Store
schema advances additively to 4 to retain optional reference evidence while accepting
schemas 1–3.

`execution_authorized` and `live_control_authorized` remain false. No scheduler,
recommendation-to-command bridge, Rachio write, retry, or autonomous watering is added.
