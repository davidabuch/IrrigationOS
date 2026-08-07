# v1.0.3 Water Requirement Pipeline Integration

IrrigationOS v1.0.3 connects the frozen Plant Water Requirement engine to the synchronized Home Assistant pipeline while remaining observation-only.

## Inputs

Each coordinator refresh uses the already-resolved curated Plant Knowledge result, the area establishment stage stored in the Landscape Digital Twin, and privacy-preserving Home Assistant location context. Season is derived deterministically from the evaluation month and hemisphere. Exact latitude and longitude are not retained in the scientific snapshot or diagnostics.

## Water Requirement execution

Each configured area receives one immutable water-requirement evaluation. Evidence-backed assessments preserve the Plant Knowledge claim value, unit, source provenance, confidence, applicability result, and explanation. Missing establishment context, unresolved plant knowledge, or unavailable hemisphere produces explicit blocker codes instead of defaults.

A partially applicable regional result remains visible as a partial assessment rather than being converted into a fabricated full match.

## Safety boundary

This milestone does not run Plant Stress, Recommendations, Planning, Scheduling, or live controller commands. Downstream stages remain explicitly blocked until their existing engines are connected to the synchronized HA pipeline.

## CI maintenance

The workflow uses Node 24-compatible GitHub action generations to remove the Node.js 20 deprecation warning from checkout and Python setup steps.
