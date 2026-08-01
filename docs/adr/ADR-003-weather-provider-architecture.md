# ADR-003: Weather Provider Architecture

- **Status:** Accepted
- **Date:** 2026-08-01

## Context

Distant Rachio weather stations may not represent a property's microclimate. Forecast and observed weather are different data classes, and no single source is always best.

## Decision

IrrigationOS owns a provider-neutral Weather Intelligence layer. Open-Meteo is the planned default forecast/ET source, NOAA/NWS is an independent United States source for forecasts and alerts, and optional Home Assistant/local sensors can provide observed conditions. All observations include source, timestamp, quality, and confidence.

## Consequences

- Essential operation does not require users to install several separate weather integrations.
- On-property observations can outrank model estimates.
- Provider disagreement affects confidence and policy rather than being hidden.
