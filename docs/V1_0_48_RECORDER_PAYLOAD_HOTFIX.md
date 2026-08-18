# v1.0.48 Recorder Payload Hotfix

## Purpose

Home Assistant Recorder reported that `sensor.irrigationos_quantitative_water_balances` exceeded the 16,384-byte state-attribute limit after v1.0.47 weather evidence became available. The aggregate entity had been serializing every complete per-area balance, including detailed evidence.

## Contract

The aggregate entity now publishes only compact summary metadata: schema/policy version, calculation timestamp, target count, state counts, aggregate reason/blocker codes, compact target status summaries, and `execution_authorized`. Detailed quantitative and evidence fields remain on the per-zone water-balance entities and in existing diagnostics/shadow audit history.

The Home Assistant regression test serializes the aggregate attributes and requires the payload to remain below 8 KiB, leaving substantial headroom under Recorder's 16,384-byte limit.

## Safety

v1.0.48 changes only Home Assistant presentation payload size. Weather ingestion, water-balance computation, controller observation, lifecycle behavior, supervised operation, unattended canary behavior, scheduling, and execution authorization are unchanged.
