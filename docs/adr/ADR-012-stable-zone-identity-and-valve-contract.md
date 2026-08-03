# ADR-012: Stable Zone Identity, Friendly Names, and Valve Contract

## Status

Accepted for IrrigationOS v0.4.3.

## Context

Irrigation zones need predictable Home Assistant identities that remain stable when a vendor name changes, a controller is replaced, or a user changes the descriptive name shown in the UI. Home Assistant dashboards, automations, history, and future HomeKit bridges must not depend on mutable Rachio names.

IrrigationOS also intends to expose future zone controls as water valves rather than generic switches so downstream ecosystems receive correct irrigation semantics.

## Decision

Each permanent controller slot has four distinct naming layers:

1. **Canonical identity** — immutable provider-neutral `area_id` used for unique IDs and persistence.
2. **Default entity ID** — deterministic slot-based IDs such as `sensor.zone_1_observation`.
3. **Friendly name** — user-editable presentation such as `Avocado Tree` or `Front Yard Grass`.
4. **Vendor name** — read-only source name retained as metadata for troubleshooting and reconciliation.

The user-facing naming priority is:

1. an explicit IrrigationOS friendly-name override;
2. otherwise the canonical fallback `Zone N`;
3. never the vendor name as the primary Home Assistant name.

A Rachio name may be blank, generic, or changed at any time without changing the primary Home Assistant presentation. It remains available only as secondary metadata.

Changing the friendly name must not change the canonical identity, unique ID, slot number, or default entity-ID contract. Reloading, rediscovering, or upgrading the integration must not create duplicate entities.

Home Assistant administrators may still manually edit an entity ID through the native entity registry. IrrigationOS does not attempt to override that platform-level capability, but it never renames entity IDs automatically after creation.

Future controllable zone entities are reserved as:

- `valve.zone_1`
- `valve.zone_2`
- through `valve.zone_16`

Those entities will use Home Assistant water-valve semantics and will not be introduced until IrrigationOS has an explicit execution-safety boundary, duration policy, attribution, and command verification. v0.4.3 remains observation-only and does not create fake valve controls.

## Consequences

- Automations and dashboards can rely on stable slot-based identities.
- Users can apply meaningful names without coupling presentation to vendor data.
- Vendor renames do not break Home Assistant history or entity references.
- Resetting Rachio zones to default names does not degrade the IrrigationOS user experience.
- Future HomeKit exposure can use native valve semantics instead of switches.
- A later execution milestone is required before `valve.zone_*` entities are created.
