# IrrigationOS v1.0.11 — Pipeline Entities and Diagnostics

## Purpose

v1.0.11 makes the completed synchronized Home Assistant pipeline observable without changing any scientific, advisory, planning, scheduling, execution, or runtime-monitoring logic.

## Entity contract

The integration exposes one stable global diagnostic sensor for each `PipelineStage`. Each sensor reads only the coordinator-cached `PipelineEvaluation` and reports the stage status, reason, blocker codes, evaluation timestamp, and pipeline algorithm version.

Each permanent irrigation-area slot also receives one stable `Pipeline output` sensor. Its state is the latest available canonical per-area output status, preferring Runtime Monitoring and falling back upstream only when a downstream result is unavailable. Attributes expose compact statuses for Water Requirement, Plant Stress, Plant Health, Recommendations, Planning, Scheduling, Execution simulation, and Runtime Monitoring together with blocker codes and available provenance identifiers/counts.

Unused permanent controller slots remain registered according to the existing area-entity lifecycle and are disabled by default until configured.

## Diagnostics

Config-entry diagnostics retain the fully redacted immutable `pipeline_evaluation` and add a compact `pipeline_summary` containing overall status, current stage, stage readiness/reasons, blocker codes, configured/complete area counts, and output counts. Secret and property-sensitive identifiers remain covered by the existing diagnostics redaction boundary.

## Safety boundary

All new entities are read-only views over `coordinator.pipeline_evaluation`. They never invoke the pipeline engine, controller adapters, Rachio APIs, Home Assistant services, valves, switches, retries, or recovery actions. Observation and simulation remain the only operating boundary.

## Validation

The milestone adds repository and Home Assistant smoke coverage for stable entity IDs, dynamic area lifecycle, diagnostics summary presence, and the non-actuating boundary.
