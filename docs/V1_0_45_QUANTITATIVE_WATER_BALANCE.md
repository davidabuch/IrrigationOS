# v1.0.45 — Quantitative Water Balance & Forecast Reconciliation

v1.0.45 adds an observational scientific boundary for determining a canonical production area's actual water deficit and separately evaluating whether qualifying forecast precipitation can provisionally cover part of that deficit.

## Three separate quantities

The actual balance contains only occurred evidence:

`actual deficit = max(0, prior carried actual deficit + newly elapsed ET0 × plant factor − newly observed effective precipitation − newly quantified irrigation credit)`

Every carried ledger event records an explicit `accounted_through` boundary. The
next evidence window must start exactly at that boundary. Overlapping windows,
replayed windows, and gaps are rejected deterministically, preventing ET,
precipitation, or irrigation evidence from being counted twice or silently skipped.

Forecast precipitation is never subtracted from that value. A versioned forecast policy may calculate:

`forecast cover = min(actual deficit, effective forecast precipitation, actual deficit × 0.80)`

The forecast cover is provisional. Residual uncovered deficit is actual deficit minus forecast cover, while the ledger preserves both the provisionally deferred amount and the full actual deficit. Forecast water never enters actual history before observation.

## Forecast policy

The v1.0.45 policy admits a forecast only when its effective lower bound is at least 5 mm, it ends within 48 hours, it was issued within six hours, source confidence is at least 0.60, and quality is `good` or `estimated`. Probability is optional and is never invented. A forecast can change urgency, not historical water received. The configurable `maximum_deficit_cover_fraction` defaults to 0.80 so forecast uncertainty always leaves at least 20% of the actual deficit provisionally uncovered; for a 10 mm deficit and 20 mm effective forecast, cover is 8 mm and residual is 2 mm.

After the forecast window closes, effective precipitation observed specifically inside that forecast window is compared with the preserved deferred amount. Rain elsewhere in the new accounting window still credits the actual balance but cannot be misattributed as forecast realization. The outcome is realized, partially realized, not realized, or incomplete. Unrealized cover remains in the actual deficit and new ET demand is added normally.

## Effective precipitation

Positive precipitation requires an explicit admitted site policy. v1.0.45 does not infer infiltration, runoff, slope, or a fraction from the current low-confidence loam label. Exactly 0 mm remains exactly 0 mm without a transformation policy. Without a policy, positive observed effective precipitation is unavailable and positive forecast rain cannot defer demand.

## ET0 and irrigation evidence

The existing provider-neutral weather domain is the source contract for reference ET0, precipitation, forecast, provenance, quality, confidence, and timestamps. No new provider or network client is added. Missing or stale ET0 fails closed.

No observed irrigation contributes an explicit 0 mm credit without requiring delivery calibration. Quantified irrigation applies its admitted depth. `WateringSession` proves that irrigation occurred, but runtime is not converted through controller application-rate metadata. Until calibrated delivered depth exists, an overlapping unquantified session blocks an authoritative numeric balance.

## Persistence and restart

Current balances are transient coordinator-owned results and begin `not_available` after restart. HA storage contains only immutable, schema-validated forecast deferral and reconciliation events. A reconciliation records effective observed precipitation and the remaining deficit as an explicit carry-forward quantity, so partial or missed rain cannot erase deferred demand on replay. Corruption fails closed. Derived balances are recomputed; persistence never restores recommendation or execution authority. The ledger is capped at 4,096 events and requires an explicit future archival migration before capacity is exceeded.

Schema-2 shadow records include the complete water-balance snapshot for audit and replay. Existing schema-1 and schema-2 actual-vs-shadow scheduling compatibility is unchanged.

`actual_net_deficit_mm` remains scientific net unmet demand. It does not populate
the production recommendation's `irrigation_depth`, because converting net deficit
to applied depth requires a later delivery/application policy. Runtime and
scheduling outputs therefore remain unavailable.

## Home Assistant

The integration exposes:

- `sensor.irrigationos_quantitative_water_balances`
- `sensor.zone_<slot>_water_balance` for configured production targets only

Attributes distinguish actual deficit, observed/effective precipitation, forecast precipitation/effective forecast, provisional cover, deferred amount, residual deficit, reconciliation state, evidence, confidence, completeness, and blockers. Provider-native identifiers are excluded.

## Safety boundary

The package has no imports from first-live delivery, supervised operation, unattended canary, Rachio transport, or execution operators. It creates no runtime or schedule, performs no retry, and never authorizes execution. `execution_authorized` and `live_control_authorized` remain false.
