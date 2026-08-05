# v0.8.0B — Curated Stress-Tolerance Evidence

## Scope

This milestone adds approved, provenance-preserving stress-tolerance claims for the eight existing curated species.

Added fields:

- `water.water_stress_sensitivity`
- `environment.heat_tolerance`
- `environment.minimum_temperature_celsius`

## Boundary

This milestone is canonical knowledge only. It adds no assessment engine, recommendation, planning, scheduling, execution, provider access, clock access, randomness, or mutable runtime state.

## Evidence behavior

- Claims remain immutable and deterministically ordered.
- Each claim identifies approved bibliographic sources.
- Minimum-temperature values preserve explicit temperature thresholds or normalized USDA hardiness-zone lower bounds in Celsius.
- Qualitative water-stress and heat-tolerance values use the existing canonical enums.
- Regional applicability is explicitly limited to the Southern California Mediterranean context.

## Curated species

- *Agave attenuata*
- *Cynodon dactylon*
- *Dymondia margaretae*
- *Heteromeles arbutifolia*
- *Lagerstroemia indica*
- *Muhlenbergia rigens*
- *Quercus agrifolia*
- *Rhaphiolepis indica*
