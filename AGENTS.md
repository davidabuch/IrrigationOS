# IrrigationOS Engineering Instructions

This file defines durable engineering, safety, development, validation, and deployment rules for the IrrigationOS repository.

These instructions apply to humans, AI coding agents, Codex, and other automated development tools working in this repository.

Read this file before modifying IrrigationOS.

---

# 1. Product Mission

IrrigationOS is a Home Assistant irrigation intelligence and management system.

Its purpose is to model the actual landscape, understand irrigation demand, observe watering behavior, generate defensible recommendations, and eventually support carefully authorized irrigation control.

The system must remain:

- deterministic where practical;
- observable;
- explainable;
- fail-safe;
- conservative around physical equipment;
- explicit about uncertainty;
- auditable;
- compatible with Home Assistant lifecycle expectations.

Correctness and physical safety take priority over convenience.

---

# 2. Core Safety Model

The fundamental control model is:

**observe → decide → command → re-observe → confirm**

Never assume that issuing a command means the physical action occurred.

Physical actions require appropriate confirmation whenever the architecture provides confirmation capability.

When state is uncertain, stale, contradictory, unavailable, or degraded, fail closed.

Do not manufacture certainty from incomplete observations.

---

# 3. Scientific Recommendation Is Not Execution Authority

This distinction is fundamental.

A scientific irrigation recommendation does not by itself authorize physical watering.

Keep separate:

1. observation;
2. scientific assessment;
3. recommendation;
4. execution authorization;
5. physical command;
6. post-command confirmation.

Do not collapse these concepts.

A recommendation such as "Increase watering for this zone by 20% for seven days" does not mean IrrigationOS may automatically execute that recommendation.

Autonomous execution requires an explicitly commissioned and authorized control path.

---

# 4. Diagnostic Watering Is Not Irrigation Credit

Operator-directed diagnostic watering may be used for:

- identifying a zone;
- observing emitters;
- inspecting coverage;
- photographing watering behavior;
- troubleshooting;
- commissioning.

Diagnostic runtime alone must NOT automatically become scientific irrigation credit.

Do not infer delivered water depth from runtime without adequate calibration or defensible delivery data.

Examples of diagnostic operations include:

- 30-second zone identification;
- short supervised watering observations;
- emitter inspection.

These operations must remain distinguishable from quantitative irrigation accounting.

---

# 5. Physical Equipment Safety

Never weaken an existing safety boundary merely to make a feature easier to implement.

Preserve appropriate checks involving:

- integration health;
- controller availability;
- controller ownership;
- observation freshness;
- confirmed observations;
- execution-boundary acknowledgement;
- active watering conflicts;
- supervised operations;
- unattended operations or canaries;
- target existence;
- target enabled state;
- target idle state;
- dispatch serialization;
- transport uncertainty;
- post-command confirmation.

If the system cannot determine whether a physical command succeeded, treat the result as uncertain.

Do not blindly retry a physical command when the first request may actually have reached the controller.

Duplicate watering is a physical side effect.

---

# 6. Degraded-State Behavior

When IrrigationOS is degraded, uncertain, stale, or missing required authority:

**observe, report, and fail closed.**

Do not autonomously command irrigation equipment from a degraded state.

Do not bypass safety checks to recover functionality.

Recovery must restore trustworthy state before normal execution resumes.

---

# 7. Production Zone Identity

The production irrigation controller currently uses these canonical controller zone numbers:

- Zone 1
- Zone 2
- Zone 4
- Zone 5

Zone 3 is intentionally absent.

Do not assume that controller zone numbers are contiguous.

Never renumber zones merely to eliminate a numerical gap.

Code should support non-contiguous controller slots.

---

# 8. Zone Identity vs. Landscape Configuration

A fundamental IrrigationOS product concept is:

**A zone is permanent hardware identity; a zone setup is a replaceable landscape profile.**

The physical/controller zone remains the same zone even when the landscape changes.

Examples:

- turf replaced with shrubs;
- sprinklers replaced with drip;
- plants removed;
- new plants installed;
- soil substantially amended.

Do not destroy physical zone identity when landscape configuration changes.

A future recommissioning workflow should retire/archive the previous landscape profile with historical context while establishing a new active profile.

Historical truth should remain reconstructable.

---

# 9. Zone-Centric Product Model

Prefer a user mental model centered around:

**My Zones → choose zone → understand / identify / maintain**

A completed zone should eventually support actions such as:

- Identify Zone;
- Add Plant;
- Edit Setup;
- Troubleshoot Plants;
- Start Over / Recommission Zone.

Avoid forcing homeowners to understand internal IrrigationOS implementation concepts when a zone-centric representation is possible.

---

# 10. Guided Zone Setup Philosophy

Zone commissioning should progressively establish:

1. zone identity and friendly name;
2. soil;
3. plants or plant groups;
4. water-delivery method;
5. sun exposure;
6. review and uncertainty.

Setup should support saving progress and continuing later.

"I don't know" is a valid answer.

Unknown information should generally reduce confidence rather than forcing the system to invent an answer.

---

# 11. Soil Modeling

Installation address or geographic location may provide a useful soil hypothesis.

It is not authoritative proof of the soil currently surrounding the plants.

Landscapes may contain:

- imported soil;
- amended soil;
- raised-bed soil;
- planter/container mixes;
- replaced topsoil.

When appropriate, distinguish natural ground from planter/raised-bed/container soil.

User observations and photographs may increase confidence.

Represent uncertainty explicitly.

---

# 12. Plant Modeling

Prefer useful plant groups over unnecessarily modeling every individual plant when plants share:

- species/type;
- irrigation delivery;
- establishment stage;
- environmental conditions.

Individual plants may still be modeled when they materially differ.

For newly added plants, useful information may include:

- plant identity;
- quantity;
- newly planted vs. established;
- approximate planting date;
- nursery/container size when useful.

Plant identity derived from images must remain confirmable/editable by the user.

Do not silently treat probabilistic identification as certain.

---

# 13. Water Delivery Matters

Plant demand alone is insufficient to determine runtime.

IrrigationOS must also understand how water reaches the landscape.

Relevant delivery types may include:

- spray sprinklers;
- rotors;
- drip emitters;
- micro-sprays;
- bubblers;
- other delivery systems.

Emitter counts, flow rates, precipitation rates, calibration measurements, and coverage relationships may become important.

Do not convert theoretical plant water need into precise runtime unless delivery information supports that conversion.

---

# 14. Troubleshooting Philosophy

Troubleshooting should correlate multiple sources of evidence where available:

- symptoms;
- current photographs;
- weather;
- ET;
- rainfall;
- watering history;
- soil;
- plant identity;
- establishment stage;
- delivery method;
- recent landscape changes.

Avoid single-signal diagnoses when evidence is incomplete.

Recommendations should explain their reasoning and uncertainty.

Temporary adjustments are generally preferable to silently changing permanent coefficients.

---

# 15. Repository Is Engineering Truth

Do not rely on conversation history, memory, handoff notes, or assumptions as authoritative repository state.

Before development, inspect the repository.

At minimum establish:

- current branch;
- current HEAD;
- working-tree status;
- relevant source implementation;
- relevant tests.

When an expected branch, commit, version, or architecture does not match reality:

**STOP and investigate.**

Do not force the repository to match an outdated prompt.

---

# 16. Live Home Assistant Is Separate Truth

Repository state and deployed Home Assistant state are separate facts.

Never assume that the live integration matches GitHub merely because version strings match.

When deployment identity matters, verify it.

Useful verification may include:

- manifest version;
- source file inventory;
- canonical tree hash;
- selected file hashes;
- runtime diagnostics.

A GitHub repository describes source truth.

Home Assistant describes deployed/runtime truth.

Neither should be inferred from the other.

---

# 17. Canonical Cross-Platform Tree Hashing

macOS and Home Assistant/Linux may use different locale collation rules.

When comparing aggregate source-tree hashes across platforms, use deterministic ordering.

Prefer `LC_ALL=C` for sorting involved in canonical tree-hash generation.

Do not interpret different aggregate hashes as proof of different source trees until ordering, exclusions, line handling, and hashing methodology have been verified.

---

# 18. macOS vs. Home Assistant Shells

Do not assume the Mac and Home Assistant shells provide identical Unix tooling.

macOS generally uses BSD userland.

Home Assistant/Linux may provide GNU or BusyBox behavior depending on environment.

Do not assume GNU-only options work on macOS.

Examples requiring caution include:

- find;
- sed;
- date;
- stat;
- readlink;
- xargs;
- hashing utilities.

When giving commands, clearly label them:

**MAC TERMINAL**

or

**HOME ASSISTANT TERMINAL**

Prefer portable commands when practical.

---

# 19. Interactive Terminal Safety

For interactive commands supplied to the project owner:

**Do not use `set -eu` as the default safety mechanism.**

Long interactive scripts may legitimately encounter optional/empty results, and abrupt shell termination can leave partially completed work with poor diagnostics.

Instead use explicit validation, return-code checks, clear STOP messages, and useful checkpoints.

Do not hide errors with excessive `2>/dev/null`.

Use `|| true` only when failure is explicitly acceptable and does not conceal a safety-critical condition.

---

# 20. Avoid Brittle Source Patching

Do not use large shell scripts or Python scripts that mutate source code through fragile exact-string replacement when direct source editing is available.

Avoid patterns such as:

- large `.replace()` patch chains;
- exact multiline string assertions;
- line-number-dependent mutation;
- shell-generated source rewrites.

These approaches become unreliable as the repository evolves and can leave partially modified trees.

AI coding agents should inspect and edit source files directly.

Terminal automation remains appropriate for:

- inspection;
- validation;
- packaging;
- hashing;
- deployment verification;
- deterministic file operations.

---

# 21. Scope Discipline

Implement the smallest coherent change that satisfies the task.

Do not perform opportunistic refactors during unrelated feature work.

Do not:

- rename unrelated APIs;
- reorganize unrelated packages;
- change unrelated formatting;
- redesign storage without need;
- alter safety contracts incidentally;
- bump versions prematurely.

If a requested feature reveals a larger architectural problem, report it before broadening scope.

---

# 22. Inspect Before Editing

Before modifying an unfamiliar subsystem:

1. inspect its implementation;
2. inspect its public API;
3. search all callers;
4. inspect relevant tests;
5. identify safety boundaries;
6. formulate a bounded plan.

Do not infer architecture from filenames alone.

Search before changing shared constants, action values, schemas, dataclasses, or function signatures.

---

# 23. Backward Compatibility

When extending an existing API, prefer backward-compatible defaults when they preserve intended semantics.

If existing guided observation is 180 seconds and a new identification feature requires 30 seconds, parameterize the duration while retaining 180 seconds as the existing default rather than globally redefining guided observation as 30 seconds.

Tests must prove old and new behavior coexist when coexistence is intended.

---

# 24. Home Assistant Lifecycle Discipline

IrrigationOS is a Home Assistant integration and must respect Home Assistant lifecycle expectations.

Avoid:

- unmanaged background tasks;
- blocking event-loop operations;
- startup work that unnecessarily delays HA;
- tasks that survive unload;
- duplicate task ownership;
- uncontrolled executor work.

Use HA-supported lifecycle/task mechanisms where appropriate.

Setup and unload must be symmetrical where resources are created.

Treat lifecycle warnings seriously even when functionality appears correct.

---

# 25. Persistent Storage Discipline

Persistent data requires special care.

Do not casually change:

- storage schema;
- identifiers;
- historical semantics;
- config-entry meaning;
- migration behavior.

When schema changes are required:

- make them explicit;
- preserve recoverability;
- test migrations;
- preserve historical truth where appropriate.

Do not create migrations for transient state.

---

# 26. Tests Are Part of the Feature

A feature is incomplete without tests appropriate to its risk.

Tests should cover:

- intended behavior;
- important backward compatibility;
- fail-closed behavior;
- invalid inputs;
- physical-command boundaries;
- uncertain transport where applicable;
- lifecycle/restart semantics where applicable.

Prefer extending existing test patterns over inventing unnecessary infrastructure.

Physical-equipment code deserves negative tests proving commands are NOT issued under invalid conditions.

---

# 27. Validation Discipline

Before reporting code complete, run the repository's actual validation stack.

Inspect repository configuration rather than inventing commands.

Typical validation may include:

- `python scripts/validate_repository.py`
- `python -m pytest -q`
- `python -m ruff check .`
- `python -m mypy custom_components tests`
- `python -m pytest -q --asyncio-mode=auto tests_ha`
- `git diff --check`

If repository tooling changes, use the current authoritative tooling.

A focused test is useful during development.

It is not a substitute for the complete validation stack before completion.

When a code failure occurs:

1. fix it;
2. rerun focused validation;
3. rerun the complete validation stack.

Distinguish code failures from environment/tooling failures.

Never conceal a failed validation command.

---

# 28. Git Discipline

Do not modify `main` directly for feature development.

Use a feature branch.

Before editing inspect:

- `git branch --show-current`
- `git rev-parse HEAD`
- `git status --short`

Unexpected dirty state must be understood before proceeding.

Do not automatically discard user work.

Do not run destructive Git operations unless the intended discarded state is known.

AI coding agents must not commit, push, merge, or create a pull request unless explicitly authorized for that task.

Preferred sequence:

1. verify clean authoritative base;
2. create/use feature branch;
3. implement bounded change;
4. run focused tests;
5. run full validation;
6. inspect diff;
7. human/ChatGPT review;
8. commit;
9. push;
10. PR;
11. CI;
12. merge.

---

# 29. Codex / Coding-Agent Rules

Before changing code, a coding agent must:

1. read this `AGENTS.md`;
2. inspect branch/HEAD/status;
3. inspect relevant source;
4. search relevant callers;
5. inspect relevant tests;
6. formulate a bounded implementation plan.

Coding agents should edit repository files directly.

They should not generate brittle patch scripts for the user to execute.

When the repository differs materially from the prompt:

**STOP and report the discrepancy.**

Do not improvise around an unknown architecture.

Unless explicitly authorized, coding agents must not:

- deploy to Home Assistant;
- access live irrigation equipment;
- start watering;
- stop watering;
- alter GitHub;
- push;
- merge;
- create releases;
- commit.

---

# 30. When to Use a Coding Agent

Use a coding agent when it materially reduces risk for:

- multi-file changes;
- repository-wide caller searches;
- API changes;
- refactors;
- migration work;
- substantial test changes;
- changes where direct repository inspection is important.

Small deterministic inspections and operational checks may be more efficiently handled with terminal commands.

Do not use coding-agent complexity merely for trivial changes.

---

# 31. Deployment Is Separate From Development

Passing tests does not authorize deployment.

Deployment requires a separate explicit decision.

Do not patch individual production files casually when the intended deployment unit is the complete integration.

Preferred deployment artifact is a complete ZIP built from the exact approved merged Git commit.

---

# 32. ZIP Packaging Rules

Build release/deployment ZIPs from the exact approved Git commit whenever practical.

A preferred approach is based on `git archive` so untracked/local files cannot accidentally enter the artifact.

The archive should have the complete integration under:

`custom_components/irrigationos/`

Before deployment verify:

- expected integration root;
- manifest exists;
- expected packages exist;
- version is correct;
- no nested `irrigationos/irrigationos`;
- no editor junk;
- no `__pycache__`;
- no `.pyc`;
- no unrelated files;
- artifact SHA256.

Never build a production ZIP from an unknown dirty working tree.

---

# 33. Home Assistant Deployment Workflow

Preferred production deployment sequence:

1. merge approved PR;
2. identify exact merged commit;
3. build complete ZIP from that commit;
4. inspect ZIP;
5. record artifact SHA256;
6. deploy complete `irrigationos` directory;
7. verify directory structure;
8. verify manifest/version;
9. run `ha core check`;
10. restart only after successful configuration validation;
11. perform focused post-restart validation;
12. inspect relevant logs/diagnostics.

Do not restart Home Assistant merely because files changed.

Configuration validation comes first.

---

# 34. Production Diagnostics

Prefer targeted, discriminating diagnostics over giant log dumps.

A good diagnostic should answer a specific question.

Examples:

- Did the integration initialize?
- Is there an IrrigationOS traceback?
- Did lifecycle cleanup succeed?
- Is the controller observation fresh?
- Did the expected command dispatch once?
- Was the physical result confirmed?

Avoid repeated broad log searches when one targeted test can discriminate between hypotheses.

---

# 35. Evidence Before Hypothesis

When debugging:

1. state the hypothesis;
2. identify evidence that would distinguish it;
3. collect that evidence;
4. update the hypothesis.

Do not repeatedly gather generic diagnostics without narrowing the problem.

Do not preserve a favored theory after contradictory evidence appears.

General lessons include:

- aggregate hash differences can result from platform-dependent sorting;
- matching version strings do not prove matching trees;
- temporal correlation does not prove a component caused a Home Assistant stall;
- lack of traceback does not prove lack of lifecycle impact.

---

# 36. Do Not Guess Physical Watering

Never invent physical watering duration merely because the user asks to water a zone.

Physical watering should use:

- an explicitly requested duration;
- an authorized existing recommendation;
- a commissioned/calibrated decision path;
- or an explicitly defined diagnostic duration.

Do not convert an uncertain recommendation into equipment runtime.

---

# 37. Human-Readable Explanations

User-facing IrrigationOS recommendations should explain:

- what IrrigationOS believes;
- why;
- confidence/uncertainty where meaningful;
- what action is recommended;
- whether the action is temporary or permanent.

Avoid exposing unnecessary internal implementation terminology to homeowners.

Engineering diagnostics may remain technical.

---

# 38. Recent Landscape Changes Are Important Evidence

The model should eventually account for meaningful changes such as:

- new plant;
- removed plant;
- turf removal;
- emitter replacement;
- irrigation conversion;
- soil amendment;
- major pruning;
- transplanting.

A landscape is not static.

Historical profiles and effective dates should make it possible to understand what was true at a given time.

---

# 39. Edit vs. Recommission

These concepts are distinct.

**Edit Setup**

Use when correcting or refining the existing landscape description.

Examples:

- correcting a plant identity;
- changing sun classification;
- correcting emitter information.

**Recommission / Start Over**

Use when the landscape fundamentally changes.

Examples:

- lawn removed and replaced with shrubs;
- sprinkler zone converted to drip;
- substantial redesign of the planted area.

Recommissioning should preserve prior history while establishing a new active landscape profile.

---

# 40. Preserve User Agency

IrrigationOS should assist rather than silently overrule.

Where evidence is uncertain:

- present the best-supported interpretation;
- explain uncertainty;
- allow correction;
- preserve the correction as appropriate.

Photo-based identification, soil inference, and troubleshooting conclusions should remain reviewable.

---

# 41. No Hidden Permanent Adaptation

Adaptive recommendations should not silently create permanent model changes.

When temporary watering changes are appropriate, represent them as temporary and reassess.

Permanent model changes should be explicit, explainable, and historically traceable.

---

# 42. Current State Does Not Belong in This File

Do NOT place rapidly changing information in `AGENTS.md`, including:

- current release number;
- current branch;
- current HEAD SHA;
- active PR number;
- commissioning elapsed time;
- today's HA Core version;
- current temporary bug;
- current deployment artifact hash.

Those facts become stale.

Keep this file focused on durable engineering rules.

Current state should be obtained from:

- Git;
- repository files;
- CI;
- Home Assistant;
- explicit development handoff/state documents.

---

# 43. Stop Conditions

Stop rather than improvise when:

- branch is unexpected;
- base commit is unexpected for a task requiring a specific base;
- working tree contains unexplained changes;
- repository architecture contradicts task assumptions;
- a safety invariant cannot be preserved;
- a physical command's target is ambiguous;
- live state is too stale to authorize a command;
- validation reveals unexplained failures;
- deployment artifact cannot be tied to an approved commit.

A clear stop with evidence is preferable to a plausible but unsafe workaround.

---

# 44. Definition of Done

For code development, "done" generally means:

- requested scope implemented;
- unrelated scope unchanged;
- safety invariants preserved;
- relevant negative tests included;
- focused tests pass;
- complete repository validation passes;
- `git diff --check` passes;
- diff reviewed;
- no unexplained working-tree changes;
- no deployment occurred unless separately authorized.

For deployment, "done" additionally means:

- artifact tied to approved commit;
- ZIP validated;
- HA configuration check passed;
- restart completed successfully;
- integration loaded;
- focused post-deployment validation passed;
- no new relevant errors observed.

---

# 45. Governing Principle

When choosing between speed and trustworthy irrigation behavior:

**choose trustworthy behavior.**

When choosing between assumption and inspection:

**inspect.**

When choosing between silent recovery and explicit uncertainty:

**report uncertainty.**

When choosing between conversational memory and repository/runtime evidence:

**trust the evidence.**
