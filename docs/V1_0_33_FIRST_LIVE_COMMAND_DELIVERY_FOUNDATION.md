# IrrigationOS v1.0.33 — First-Live Command Delivery Foundation

v1.0.33 introduces the audited physical transport primitive required for a future supervised first-live trial, while retaining a hard-disabled release gate.

## Physical transport primitive

The Rachio-specific boundary exposes only two operations:

- `PUT /public/zone/start` for one zone with a maximum IrrigationOS runtime of 120 seconds.
- `PUT /public/device/stop_water` as the device-wide emergency stop path.

No schedule start, multi-zone start, device enable/disable, rain-delay, or configuration mutation operation is exposed by this boundary.

## Release safety boundary

`PHYSICAL_FIRST_LIVE_DELIVERY_ENABLED` remains `False` in v1.0.33. Therefore an otherwise `first_live_trial_eligible` commissioning state remains `release_gate_disabled` and cannot transition into physical delivery through IrrigationOS runtime code.

The release adds no Home Assistant service, button, scheduler callback, or coordinator execution method for the transport. Autonomous scheduling remains disabled. Native controller and zone identifiers are not emitted in delivery diagnostics.

## Why add a disabled transport

Separating the network primitive from its future enablement allows the request shape, endpoint allowlist, runtime ceiling, error handling, diagnostics, and emergency-stop path to be reviewed and tested before any release can use them.

The next milestone must bind canonical controller/area slots to the exact native Rachio device/zone identifiers, define the explicit operator execution action, consume the single-use commissioning approval before network dispatch, and prove start/stop acknowledgement plus post-run reconciliation before the release gate can be considered for enablement.
