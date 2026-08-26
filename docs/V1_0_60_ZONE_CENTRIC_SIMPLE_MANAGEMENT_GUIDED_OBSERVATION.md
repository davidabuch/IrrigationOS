# v1.0.60 — Zone-Centric Simple Management & Guided Observation

## Purpose

This milestone makes each configured controller zone the homeowner-facing unit of management. The same **Manage zones** path supports first setup, later plain-language updates, photos, review, bounded observation, and entry to existing Advanced tools.

## Zone management

Zone status is derived from canonical commissioned evidence as **Not set up**, **Partially set up**, **Needs review**, or **Set up**. Existing facts prepopulate the simple form. A confirmed update changes the existing canonical zone and records the prior plant snapshot; it does not create a parallel simple-mode record.

## Guided observation

An explicit operator may start the selected configured zone for at most 180 seconds and may stop it early. Each start performs a fresh health, observation, conflict, controller, and target preflight. Transport is attempted once. The action has no automatic repeat and no retry. State is transient, is reconciled from controller observation, and resets on restart without resuming watering.

Rachio's safe stop primitive is controller-wide. IrrigationOS permits it only for the locally active selected observation and surfaces transport or post-command observation failures rather than assuming success.

## Photos

The Home Assistant UI accepts multiple image selections through its media selector. Persisted records contain a stable evidence ID, canonical property/zone association, timestamp, source, optional note, running-context flag, privacy and retention policy, and an opaque media reference. Raw bytes are never placed in commissioning state, diagnostics, or Recorder attributes. Direct camera behavior is limited by the Home Assistant media-source frontend; no custom upload endpoint is introduced.

## Restart and performance

Store schema 7 restores only lightweight photo metadata. There is no startup image scan, analysis, network call, timer, task, or background loop. Guided observation state is not persisted.

## Safety

This milestone adds no scheduler, recommendation-to-command bridge, autonomous watering, retry, or hidden authority. `execution_authorized` and `live_control_authorized` remain false. Existing first-live, supervised-operation, unattended-canary, confirmation, runtime, validation, and no-retry semantics are unchanged.
