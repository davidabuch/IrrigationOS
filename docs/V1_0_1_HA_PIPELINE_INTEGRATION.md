# v1.0.1 Home Assistant Pipeline Integration

## Purpose

This milestone introduces one immutable `PipelineEvaluation` snapshot per successful
Home Assistant coordinator refresh. All pipeline sensors and diagnostics read from
that same cached object.

## Truthful staged integration

The current coordinator can provide controller observations and Landscape Digital
Twin profiles. It does not yet collect every weather, plant-knowledge, and visual
assessment input required by the scientific engines.

The pipeline snapshot therefore reports explicit stage readiness and typed blocker
codes. It never fabricates water requirement, stress, health, recommendation, plan,
schedule, execution, or runtime outputs.

## Home Assistant entities

- Pipeline status
- Current pipeline stage
- Pipeline version
- Last pipeline evaluation

The current-stage sensor includes per-stage status, reason, and blocker attributes.

## Safety

This milestone is observation-only. It registers no hardware services and issues no
Rachio or Home Assistant actuation commands.
