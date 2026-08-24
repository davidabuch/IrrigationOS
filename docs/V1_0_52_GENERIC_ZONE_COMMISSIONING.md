# v1.0.52 — Generic Zone Commissioning Foundation

## Architecture

v1.0.52 replaces the Zone-1-shaped commissioning boundary with an immutable generic zone aggregate.
Stable property/zone identity, plant details, demand-source mode, delivery linkage, and landscape
events are represented as structured data consumed by reusable engines.

The milestone reuses rather than duplicates the existing domains:

- Landscape Intelligence remains the factor-resolution input;
- Landscape Digital Twin remains the canonical long-term property model and fact-history boundary;
- Water Delivery owns emitter/component calibration;
- Visual Assessment owns provider-neutral structured photo findings; and
- factor resolution remains generic and unchanged at algorithm version 1.1.0.

## Onboarding modes

- `manual_plant_profile` carries user-confirmed plant identity, planting date, source-container size,
  current size, establishment state, and independent delivery linkage.
- `user_calibrated_baseline` carries a trusted runtime and exact reference condition without inventing
  weather scaling.
- `photo_ai_derived` references structured assessment/finding IDs without storing images or provider
  payloads.
- `hybrid` combines at least two of those evidence kinds without collapsing provenance.

## Landscape change and compatibility

Immutable add/remove events retain prior plant snapshots, so replacement does not overwrite history.
Delivery links may remain unresolved. The advisory compatibility assessment requests delivery
information or review when needed; it does not infer emitter performance, calculate runtime, or issue
commands.

## Backward compatibility

Zone 1 is built through the generic aggregate and then adapted to the existing
`LandscapeIntelligenceProfile`. Its mixed planting, incidental mature palms, establishment blocker,
unresolved ornamental group, factor evidence, diagnostics keys, and schema-1 persistence boundary are
preserved. The old public builder remains a regression-fixture API.

## Safety

All new results are advisory. `execution_authorized` and `live_control_authorized` remain false. No
Home Assistant service, scheduler, physical-operation path, Rachio transport behavior, retry policy,
or current authorization gate changes in v1.0.52.

