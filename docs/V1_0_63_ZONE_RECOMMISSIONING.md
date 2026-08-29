# IrrigationOS v1.0.63 — Zone Recommissioning / Start Over

## Purpose

v1.0.63 adds a deliberate homeowner-facing way to replace the current landscape interpretation of an installed irrigation zone without replacing the zone itself.

The governing invariant is:

> Physical zone identity is permanent; landscape/setup state is replaceable.

The Zone Home exposes **Start over / Recommission** only for a currently configured setup. A separate confirmation screen explains the effect before any durable state changes. Cancelling or merely opening that screen performs no save.

## What remains permanent

Recommissioning preserves the canonical property and zone IDs, controller and area slots, homeowner display name, controller binding, and Home Assistant entity/device relationship. The zone is not deactivated and no replacement physical zone is created.

Opaque photo references remain associated with the same property and zone. Canonical Water Delivery profiles also remain because they may be reusable or shared independently of the retired planting. Other zones are untouched.

## What becomes unresolved

The active aggregate clears current plant groups, plant commissioning details, plant-specific delivery links, calibrated baseline assumptions, setup-specific conflicts, and their resolutions. It retains one explicit unresolved demand source and advisory-only authority. The Zone Home consequently reports **Not set up** and routes **Set up this zone** to the existing simple commissioning workflow.

## Historical evidence

The prior active setup cannot be represented truthfully by the existing plant-only event snapshot: calibrated baselines, conflicts, resolutions, and delivery links would otherwise be lost. Schema 7 therefore adds `ZONE_RECOMMISSIONED` with a non-recursive `LandscapeSetupSnapshot` containing the complete retired active setup. Existing landscape events remain unchanged and chronological.

The commissioning Store schema advances from 7 to 8. Loading schemas 1–7 remains additive and deterministic; migration does not fabricate a recommissioning event for older data.

## Persistence and safety

The manager constructs one candidate aggregate, writes the complete Store payload once, and publishes in-memory state only after the save succeeds. A failed save leaves the active setup and all related collections unchanged.

Recommissioning is evidence lifecycle only. It creates no watering command, guided-observation session, scheduler action, retry, background task, delivery-depth credit, execution authorization, or live-control authorization. v1.0.62 manual-stop confirmation behavior is unchanged.
