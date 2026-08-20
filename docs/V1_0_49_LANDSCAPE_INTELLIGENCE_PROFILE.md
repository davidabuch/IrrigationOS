# v1.0.49 — Landscape Intelligence Profile v1

v1.0.49 adds an advisory, durable landscape-intelligence boundary without changing quantitative water-balance or hardware-control authority.

## Zone 1 commissioning seed

The human-reviewed profile records a mixed micro-spray hydrozone using predominantly blue approximately 3-foot microjets. It records mature palms as established incidental plants that do not control zone demand; a roughly three-year-old fig; establishing roughly one-to-two-year-old citrus; passion fruit; intentionally irrigated Podocarpus with one two-sided microjet serving two trees; drought-tolerant ornamentals; and directly irrigated Peruvian lilies with an initial structured observation of visible stress.

The initial Peruvian-lily observation records reduced vigor, sparse foliage, and browning/dieback as observations only. Water stress remains possible rather than diagnosed. No source photos are stored.

## Longitudinal observations

Plant-health observations are immutable, timezone-aware structured findings. New observations append rather than overwrite prior findings. Derived trend vocabulary is `improving`, `stable`, `worsening`, or `insufficient_history`. A single observation cannot establish a trend.

## Recorder boundary

Detailed plant groups and longitudinal observation history belong in integration storage and diagnostics. Home Assistant state summaries must remain compact; regression tests deliberately grow history beyond 8 KiB while keeping the compact summary below 8 KiB.

## Scientific and safety boundary

Plant and landscape factors remain unresolved in this milestone. v1.0.49 does not remove `plant_factor_unresolved`, change quantitative water-balance calculations, alter schedules or runtimes, issue Rachio commands, or grant execution/live-control authority. Health observations cannot directly authorize runtime adjustment.
