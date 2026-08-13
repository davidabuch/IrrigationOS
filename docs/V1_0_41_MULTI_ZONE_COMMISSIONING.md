# v1.0.41 — Multi-Zone Commissioning & Validated Target Registry

## Purpose

v1.0.41 replaces the single-target operational eligibility rule with a durable registry of canonical targets that individually passed supervised first-live commissioning. This allows another configured target, such as controller slot 1 / area slot 1, to complete the same bounded first-live process without invalidating the previously validated controller slot 1 / area slot 2.

## Validated-target registry

Registry identity is exactly `(controller_slot, area_slot)`. Each immutable record contains only its canonical slots, validation timestamp, privacy-safe source attempt ID, requested and observed runtime, PASS acceptance status, and acceptance and registry schema versions. Provider-native Rachio controller and zone IDs are neither stored nor exposed.

A target is inserted or refreshed only after:

1. its exact first-live trial produces a structured `pass` record;
2. that latest first-live acceptance is durably saved; and
3. the updated registry is durably saved.

The in-memory registry changes only after storage succeeds. A failed registry save therefore cannot authorize a new target and cannot remove previously durable in-memory targets. FAIL and INDETERMINATE records never enter the registry. Repeated PASS evidence replaces the same canonical key rather than creating a duplicate.

## v1.0.40 migration

On the first v1.0.41 initialization, an absent or unmigrated empty registry is seeded only when the persisted latest v1.0.40 first-live acceptance is `pass`. The exact canonical controller and area slots and evidence fields are copied from that structured record. FAIL, INDETERMINATE, missing, or malformed evidence creates no eligibility.

The registry persists a migration-completed marker. This makes backfill idempotent and prevents an intentionally revoked target from being recreated on restart. Historical JSONL is not parsed to infer additional targets.

## Commissioning and operational eligibility

The existing options-flow target selector continues to offer configured enabled canonical areas. Every new target must independently pass the unchanged first-live safety gates, exact confirmation phrase, and 120-second limit. A PASS adds only that target; other validated targets remain unchanged.

The supervised operational service now checks exact registry membership instead of comparing the requested target to the latest first-live acceptance. An absent target receives `target_not_validated`. Health, observation freshness and quality, ownership, boundary review, integrated safety, no-conflict, availability, idle-state, exact confirmation, runtime, and no-retry rules remain unchanged.

`sensor.irrigationos_validated_targets` exposes the count and privacy-safe ordered records. Diagnostics expose the same redacted summary. An internal durable revocation method removes one exact canonical target without affecting others.

## Restart and authority boundary

Registry contents restore after restart, but no commissioning approval, operation monitor, command, or retry resumes. v1.0.41 adds no autonomous irrigation, schedules, unattended commands, broader target eligibility, command retry, controller-ownership change, or dependency on Home Assistant's official Rachio integration.
