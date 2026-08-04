# ADR-016: Environmental Weather Domain

- **Status:** Accepted for IrrigationOS v0.6.0
- **Date:** 2026-08-03

## Context

IrrigationOS will eventually need environmental intelligence and irrigation planning, but those
capabilities require a stable representation of the weather inputs they consume. Provider
payloads differ in field names, units, forecast granularity, quality indicators, missing-value
semantics, update schedules, and condition vocabularies. Passing those payloads directly into
planning would couple safety-relevant logic to a vendor and make provenance difficult to audit.

Weather data also has multiple temporal meanings. A current observation, a historical sample, an
hourly forecast, and a daily forecast are not interchangeable. Every individual value must retain
when it applies, where it came from, how trustworthy it is, and whether it was verified.

This milestone needs only a canonical environmental record. It must not infer landscape effects,
calculate derived intelligence, recommend irrigation, or communicate with external systems.

## Decision

### Independent canonical domain

The Environmental Weather Domain lives in `custom_components/irrigationos/weather/`. It is a pure
Python domain package with frozen, slotted dataclasses, stable string enums, strict construction
validation, and deterministic plain-dictionary serialization.

This layer exists independently of four future concerns:

1. **Weather providers** acquire data, authenticate, translate units and condition codes, handle
   transport failures, and construct validated canonical records. Provider SDKs, endpoint types,
   credentials, retries, and raw payloads do not enter this domain.
2. **Environmental intelligence** interprets canonical observations and forecasts across time and
   landscape context. This domain records facts but derives no environmental signal.
3. **Irrigation planning** may later consume canonical weather alongside soil, plant, water-demand,
   and delivery models. This domain neither computes demand nor proposes watering.
4. **Execution** owns any future authorized controller operation. Weather records contain no
   command, schedule, valve, controller, or execution interface.

The package has no Home Assistant entity, persistence, network, OpenAI, controller, or weather API
dependency.

### Weather fact envelope

Every environmental value uses `WeatherFact[T]`. A fact preserves:

- a typed value or explicit unknown;
- confidence from 0.0 through 1.0;
- provider-neutral `WeatherProvenance`;
- `WeatherVerificationStatus`;
- a timezone-aware observation or applicability timestamp; and
- `WeatherQualityMetadata`.

Provenance names the logical source and classifies it as station, forecast, reanalysis, manual, or
other. Optional source references and methods are non-secret identifiers or descriptions, not API
credentials or raw responses.

Quality is classified as good, estimated, suspect, or unavailable and may include stable flags,
sample count, and a reason. Unknown facts require zero confidence and unavailable quality; known
facts cannot claim unavailable quality. This makes missingness explicit rather than substituting
unsafe defaults.

### Canonical environmental facts

`EnvironmentalWeatherFacts` provides a consistent set of facts where applicable:

- air temperature in degrees Celsius;
- relative humidity in percent;
- dew point in degrees Celsius;
- wind speed and gust in meters per second;
- wind direction in degrees from zero inclusive to 360 exclusive;
- precipitation and snowfall in millimeters;
- precipitation probability in percent;
- rain rate in millimeters per hour;
- cloud cover in percent;
- solar radiation in watts per square meter;
- UV index;
- barometric pressure in hectopascals;
- visibility in meters;
- canonical weather condition;
- sunrise and sunset as timezone-aware timestamps; and
- provider-supplied reference evapotranspiration, ET₀, in millimeters.

The domain validates units through field contracts and rejects non-finite values, impossible
percentages, negative accumulations and rates, invalid wind bearings, naive timestamps, raw bytes,
and invalid sunrise/sunset ordering. It does not convert units or calculate any listed fact.
Reference ET₀ is accepted only as an externally observed or forecast fact with full provenance; it
is not computed here.

### Temporal records

The canonical point and period records are:

- `CurrentWeatherObservation`, the most recent point observation for a canonical location;
- `HistoricalWeatherObservation`, an immutable point observation retained in history;
- `HourlyWeatherForecast`, a bounded forecast period with a validity interval;
- `DailyWeatherForecast`, a local calendar-day forecast with bounded validity plus typed daily
  minimum and maximum temperature facts;
- `ObservationWindow`, an ordered bounded collection of historical observations; and
- `ForecastWindow`, ordered bounded hourly and/or daily forecast collections.

Canonical IDs do not derive from provider names or mutable labels. Location IDs identify the place
to which weather applies without embedding a provider station identity.

All facts in a point record share its observation timestamp. Forecast facts use the period's
`valid_from` as their applicability timestamp. Windows require one location, unique IDs, ordered
non-duplicate timestamps, contained periods, and no overlap within the same forecast granularity.
Hourly and daily collections may cover the same time because they are distinct resolutions.

### Serialization and lifecycle boundary

Every public model serializes deterministically: enums become stable strings, dataclasses become
plain dictionaries, tuples become ordered lists, dates and timestamps use ISO 8601, and nested
records retain declaration order. Serialization enables future adapters and audit records but does
not write data or choose a persistence format.

These models do not decide freshness, merge sources, interpolate missing values, select a preferred
provider, or revise a record. Those operations require explicit future policies outside this
canonical representation.

### Explicitly deferred intelligence

ADR-016 does not implement or define algorithms for:

- runoff estimation;
- infiltration;
- effective rainfall;
- drying index;
- water deficit;
- Santa Ana detection;
- marine layer detection;
- heat-wave detection;
- freeze intelligence; or
- irrigation recommendations.

These are future environmental-intelligence and planning milestones. Keeping them outside the
weather record prevents calculated conclusions from being confused with observed or forecast
facts.

### Safety boundary

Environmental records are descriptive inputs only. They cannot start or stop irrigation, change a
schedule, set a rain delay, modify a Landscape Digital Twin, approve an adjustment, or deliver a
controller command. No recommendation logic exists in this package.

## Consequences

- Future provider adapters can change without changing planning-facing weather identities or
  units.
- Every weather input remains auditable through confidence, provenance, verification, timestamp,
  and quality metadata.
- Current, historical, hourly, and daily data cannot be silently interchanged.
- Missing weather remains explicit and cannot become an invented zero.
- Future intelligence can operate on validated canonical inputs while retaining its own separate
  provenance and algorithms.
- This milestone introduces no runtime integration, external traffic, storage, weather
  calculation, recommendation, or irrigation execution.

## Deferred decisions

- Provider protocols, provider priority, failover, retries, rate limits, and unit translation.
- Persistence, retention, compaction, corrections, and forecast-version history.
- Location privacy, station matching, spatial interpolation, and microclimate selection.
- Freshness thresholds, source reconciliation, gap filling, and uncertainty propagation.
- All environmental intelligence and irrigation-planning topics explicitly listed above.
