# v1.0.47 Weather Evidence Ingestion

## Scope

v1.0.47 connects the existing canonical weather domain to live read-only evidence without expanding irrigation authority.

## Forecast evidence

The single available Home Assistant weather entity remains the preferred forecast authority. IrrigationOS requests its hourly forecast through Home Assistant's `weather.get_forecasts` service and normalizes up to 48 hours. The weather entity's source `last_updated` timestamp is retained as `issued_at`; routine IrrigationOS evaluation time is not substituted for source time. Zero precipitation is preserved as known zero evidence. Missing precipitation probability remains missing.

## Recent ET0 and precipitation evidence

IrrigationOS queries Open-Meteo's Historical Forecast API for recent hourly precipitation and FAO-56 reference evapotranspiration (ET0). This is model-derived historical weather evidence, not a local rain-gauge measurement, so it is explicitly classified as `estimated` with reduced confidence. It must never be described as sensor-verified precipitation.

The request uses Home Assistant's configured latitude and longitude only at runtime. Exact coordinates are not persisted in canonical weather records, water-balance evidence, or diagnostics.

Open-Meteo is refreshed no more often than every 30 minutes. A last-known-good response may remain usable for at most two hours after a transient source failure; after that, the evidence fails closed to unavailable. Home Assistant hourly forecasts are also bounded to a 30-minute refresh cadence unless the source weather entity's `last_updated` timestamp changes, and the service response is protected by a ten-second timeout. A cached HA forecast older than two hours fails closed to unavailable.

## Accounting

Canonical ET0 and historical precipitation are admitted to the quantitative water-balance engine without estimation of missing values. Forecast precipitation remains provisional and separate from historical water received. Accounting advances only through the newest fully completed hourly weather interval; it never marks the partial current hour as accounted. When a persisted forecast ledger event carries a deficit forward, the next evidence window begins exactly at the prior `accounted_through` boundary so evidence cannot overlap or silently skip a partial hour.

A site-specific effective-precipitation policy and quantified irrigation-delivery calibration are intentionally not introduced by this milestone. If those facts are required and unavailable, the existing water-balance engine continues to block the affected calculation.

## Safety boundary

Weather ingestion is read-only. It adds no scheduler, timer, retrying command path, controller transport, execution authorization, or Live-mode promotion. `live_control_authorized` and `execution_authorized` remain false except for the already-existing separately gated supervised/canary boundaries.
