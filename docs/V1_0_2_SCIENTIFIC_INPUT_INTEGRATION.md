# v1.0.2 Scientific Input Integration

IrrigationOS now normalizes current conditions from Home Assistant and resolves each
landscape area's plant identity against the curated Plant Knowledge library.

## Deterministic source selection

- Exactly one available `weather.*` entity is selected automatically.
- No available weather entity produces `weather_entity_unavailable`.
- Multiple available weather entities produce
  `multiple_weather_entities_require_selection`; IrrigationOS does not guess.

Temperature, pressure, and wind speed are normalized to Celsius, hPa, and meters per
second. Missing temperature or humidity remains an explicit blocker.

## Plant knowledge

Each landscape profile is resolved from its plant description or display name against
the curated library. Unresolved identities remain visible as
`plant_knowledge_profile_unresolved`.

## Safety and scope

This milestone remains observation-only. It does not call Home Assistant services,
Rachio write endpoints, valves, or schedules. Water Requirement remains blocked until
seasonal and establishment context are configured in a later milestone.
