# IrrigationOS Architecture Specification v1.0

**Status:** Canonical design baseline
**Date:** July 30, 2026
**Initial controller:** Rachio
**Target platform:** Home Assistant custom integration installed through HACS

---

## 1. Purpose

IrrigationOS is a Home Assistant-native irrigation operating system that determines whether each landscape zone needs water, calculates an appropriate runtime, explains the decision, and executes irrigation safely through a controller adapter.

The initial release supports Rachio directly through the Rachio cloud API. It does not require Home Assistant's existing Rachio integration.

IrrigationOS is not merely a replacement interface for a sprinkler controller. It is intended to become a controller-independent decision, execution, safety, and accountability platform for residential irrigation.

---

## 2. Product Goals

IrrigationOS must:

1. Install as one HACS custom integration.
2. Connect directly to Rachio using a user-supplied Rachio API key.
3. Discover the Rachio account, controllers, zones, schedules, and identifiers automatically.
4. Require no manually entered Rachio Person ID, controller ID, zone ID, or Home Assistant entity ID.
5. Retrieve its own weather data by default.
6. Recommend mapped soil characteristics from the installation location.
7. model water demand and estimated root-zone moisture independently for each zone.
8. begin in a non-controlling observation mode.
9. explain every irrigation recommendation and execution decision.
10. distinguish IrrigationOS commands from commands issued through the Rachio app, physical controller, Home Assistant, or another automation.
11. fail safely during API, weather, restart, or state-reconciliation problems.
12. preserve an auditable event history through a Flight Recorder.
13. support additional irrigation-controller adapters later without rewriting the decision engine.
14. feel like a native Home Assistant integration rather than a Rachio application embedded in Home Assistant.

---

## 3. Non-Goals for v1

The first release will not attempt to:

- replace every advanced function in the Rachio mobile application;
- guarantee exact soil moisture without calibration or physical sensors;
- infer application rate or flow with perfect accuracy from controller metadata alone;
- enable automatic watering immediately after installation;
- support multiple controller brands in the first production release;
- require the user to create YAML, helpers, template entities, or automations;
- use HomeKit presentation helpers as a source of truth;
- control irrigation when system state cannot be reconciled safely.

---

## 4. Architectural Principles

### 4.1 One integration

A user installs IrrigationOS once through HACS and completes setup through Home Assistant's Config Flow.

External Home Assistant weather, soil, and Rachio integrations are optional enhancements, not prerequisites.

### 4.2 Direct controller ownership

IrrigationOS owns its Rachio API client and creates its own Home Assistant devices and entities.

Home Assistant's existing Rachio integration is not required.

During development, the existing integration may remain installed temporarily for parallel validation. It is not part of the production dependency chain.

### 4.3 Discovery over manual configuration

The installer asks only for information that cannot be discovered reliably.

At minimum, this includes the Rachio API key. IrrigationOS then retrieves the account identity, controllers, zones, and associated identifiers automatically.

### 4.4 Internal IDs over Home Assistant entity IDs

Higher-level IrrigationOS code must never depend directly on Home Assistant entity IDs.

Example internal reference:

```yaml
zone_id: front_yard_street
controller_adapter: rachio
controller_native_zone_id: "<opaque Rachio zone ID>"
```

The decision engine references `front_yard_street`, not `switch.irrigationos_front_yard_street` and not a native Rachio identifier.

### 4.5 Controller-independent core

The decision engine communicates only with a controller-adapter interface.

```text
Decision Engine
      |
      v
Execution Engine
      |
      v
Controller Adapter Interface
      |
      v
Rachio Adapter
      |
      v
Rachio Cloud API
```

Future adapters may include Hydrawise, Rain Bird, OpenSprinkler, Orbit B-hyve, ESPHome, or a generic Home Assistant entity adapter.

### 4.6 Observation before control

Every installation begins in Observation mode. Automatic execution remains unavailable until commissioning requirements are satisfied.

### 4.7 Explainability

Every recommendation, skip, delay, shortening, extension, and execution result must include machine-readable reason codes and a human-readable explanation.

### 4.8 Safety authority is centralized

All live watering commands pass through one Execution Engine and one safety gate. No platform module, entity handler, service, or automation may bypass that authority.

### 4.9 Actual state and intended state remain separate

IrrigationOS must track:

- what it intends;
- what command it issued;
- what the controller reports;
- what was observed externally;
- who currently owns the active watering session.

### 4.10 Credentials never enter diagnostics

The Rachio API key and any future provider secrets must never appear in logs, diagnostics exports, entity attributes, traces, error messages, or Flight Recorder payloads.

---

## 5. System Layers

```text
Home Assistant UI and Services
            |
            v
Configuration and Entity Layer
            |
            v
IrrigationOS Coordinator
   |         |          |
   v         v          v
Weather   Soil/Plant   Controller State
   \         |          /
    \        v         /
     -> Decision Engine
             |
             v
       Recommendation Store
             |
             v
        Execution Engine
             |
             v
     Command Attribution Journal
             |
             v
       Ownership Manager
             |
             v
       Controller Adapter
             |
             v
          Rachio API

All major transitions -> Flight Recorder
```

### 5.1 Configuration and entity layer

Responsibilities:

- Config Flow and Options Flow;
- devices and entity registration;
- user-facing services;
- repairs and setup issues;
- translations;
- diagnostics export;
- presentation of recommendations and system health.

### 5.2 Coordinator

Responsibilities:

- scheduled cloud refreshes;
- controller-state polling;
- weather refreshes;
- state reconciliation;
- update throttling;
- API backoff;
- coordinator health.

### 5.3 Decision Engine

Responsibilities:

- calculate zone-level water balance;
- calculate irrigation need;
- apply weather, rain, soil, plant, seasonal, and restriction rules;
- produce recommendations without issuing commands;
- generate reason codes and explanations;
- remain deterministic for a given input snapshot and policy version.

### 5.4 Execution Engine

Responsibilities:

- verify operating mode;
- validate recommendation freshness;
- verify ownership and safety state;
- apply watering restrictions;
- create a command-journal entry;
- issue the controller command;
- verify acknowledgement and resulting state;
- stop irrigation when required;
- record success, partial success, rejection, timeout, or failure.

### 5.5 Ownership Manager

Allowed session owners:

```text
NONE
IRRIGATIONOS
EXTERNAL
SAFETY
```

Priority:

```text
SAFETY > EXTERNAL > IRRIGATIONOS > NONE
```

All ownership changes pass through the Ownership Manager.

### 5.6 Command Attribution Journal

Before every live command, IrrigationOS records:

- command ID;
- source;
- controller;
- target zone;
- action;
- requested duration;
- issue time;
- expected acknowledgement window;
- expected resulting state.

Observed state transitions are matched against recent pending commands. Unmatched transitions are classified as external activity.

### 5.7 Flight Recorder

The Flight Recorder stores an append-only, structured event stream sufficient to reconstruct why a recommendation was made and what happened during execution.

It must support redaction, bounded retention, diagnostics export, and future hash-chain integrity validation.

---

## 6. Installation and Onboarding

### 6.1 Distribution

- GitHub repository
- HACS custom repository installation
- Home Assistant restart only when required by Home Assistant
- Config Flow-based setup
- updates delivered through HACS

No manual copying of component files is part of the supported installation path.

### 6.2 Initial Config Flow

#### Step 1 — Welcome

Explain that IrrigationOS will connect directly to the irrigation controller and will begin in Observation mode.

#### Step 2 — Rachio API key

User-facing instruction:

> In the Rachio app, open Profile, select API Key, copy the key, and paste it here. IrrigationOS will validate it and discover your controllers and zones automatically.

Requirements:

- key validation before continuing;
- no key echo after submission;
- duplicate-account detection;
- useful handling of invalid, unauthorized, rate-limited, and unreachable states.

#### Step 3 — Account and controller discovery

IrrigationOS retrieves and displays:

- account identity;
- discovered controllers;
- controller online/offline state;
- controller name;
- serial or model metadata when available;
- discovered zones;
- enabled/disabled zone state.

A multi-controller account may select one or more controllers. The initial implementation may constrain a Config Entry to one controller if this materially simplifies correctness, but the internal model must not assume only one controller forever.

#### Step 4 — Home location

Use Home Assistant latitude, longitude, elevation, unit system, and timezone by default.

The user may override the irrigation location when the controller serves a different property.

#### Step 5 — Weather

Default provider:

```text
Open-Meteo
```

Properties:

- no API key;
- global availability;
- location-based forecast and historical observations when supported;
- built-in fallback and freshness checks.

Optional later sources:

- Home Assistant weather entity;
- NOAA/National Weather Service for US installations;
- personal weather station;
- local rain gauge;
- local outdoor temperature or humidity sensors;
- premium weather provider.

#### Step 6 — Soil recommendation

Use location-based USDA SSURGO data in the United States when available.

Display:

- mapped soil series or class;
- recommended texture;
- confidence;
- source;
- warning that imported landscaping soil may differ from native mapped soil.

User choices:

- accept recommendation;
- choose another soil;
- defer and configure later;
- override per zone later.

For locations without SSURGO coverage, use a guided soil-texture selection workflow.

#### Step 7 — Zone setup

For each discovered zone, display available controller metadata and ask only for unresolved landscape information.

Potential fields:

- display name;
- plant or landscape type;
- irrigation method;
- sun exposure;
- slope;
- soil override;
- root depth;
- application rate;
- flow rate;
- runoff sensitivity;
- cycle-and-soak preference;
- enabled for modeling;
- enabled for eventual automatic control.

The wizard should provide smart defaults and allow completion with minimal information.

#### Step 8 — Review

Show:

- controller;
- zones;
- weather source;
- soil source;
- location;
- initial mode;
- any missing calibration values;
- limitations that prevent later live commissioning.

#### Step 9 — Start Observation mode

The integration creates devices and entities and begins collecting data. It does not water automatically.

---

## 7. Operating Modes

### 7.1 Diagnostics

Purpose:

- verify credentials;
- inspect API reachability;
- discover controller capabilities;
- inspect state reconciliation;
- test weather and soil providers;
- expose no automated decisions or live control.

### 7.2 Observation

Purpose:

- calculate recommendations;
- observe real controller activity;
- record manual and Rachio-scheduled runs;
- compare modeled recommendations with actual watering;
- accumulate calibration evidence;
- issue no automatic watering commands.

Observation is the default mode.

### 7.3 Simulation

Purpose:

- exercise the full decision and execution plan;
- create simulated commands and expected outcomes;
- test ownership and safety logic;
- never send live start or stop commands to the controller.

### 7.4 Live

Purpose:

- allow approved recommendations to execute through the controller adapter;
- verify every command and resulting state;
- stop or suspend safely when invariants fail.

Live mode requires explicit commissioning and user confirmation.

---

## 8. Commissioning Gates

Live mode cannot be enabled unless all mandatory gates pass.

Minimum gates:

1. Valid Rachio credentials.
2. Controller reachable and state readable.
3. All controlled zones mapped to stable internal IDs.
4. Weather source healthy and freshness validated.
5. Timezone and location validated.
6. At least one complete observation period.
7. Simulation completed without unresolved critical errors.
8. Command-attribution test passed.
9. External start and stop detection passed.
10. Restart recovery tested.
11. Emergency stop capability tested.
12. Zone maximum runtime configured.
13. Watering restrictions configured or explicitly acknowledged as unavailable.
14. User explicitly enables Live mode.

Recommended additional gates:

- application rate measured or accepted with a low-confidence warning;
- runoff/cycle-and-soak behavior tested;
- local rain measurement calibrated;
- flow data available or lack acknowledged.

Live mode may be enabled per zone rather than globally.

---

## 9. Rachio Adapter

### 9.1 Responsibilities

The Rachio adapter must:

- authenticate using the API key;
- retrieve the account identity automatically;
- discover controllers and zones;
- normalize controller and zone metadata;
- read current controller state;
- read active watering state;
- read zone state where available;
- start a zone for a bounded duration;
- stop watering;
- observe Rachio schedules and rain delays where exposed;
- classify API errors;
- apply rate limiting and exponential backoff;
- expose capability flags to the core;
- never expose credentials to higher layers.

### 9.2 Adapter interface

Conceptual interface:

```python
class IrrigationControllerAdapter:
    async def async_validate_credentials(self) -> AccountIdentity: ...
    async def async_list_controllers(self) -> list[Controller]: ...
    async def async_list_zones(self, controller_id: str) -> list[Zone]: ...
    async def async_get_state(self, controller_id: str) -> ControllerState: ...
    async def async_start_zone(self, zone_id: str, duration_s: int, command_id: str) -> CommandReceipt: ...
    async def async_stop(self, controller_id: str, command_id: str) -> CommandReceipt: ...
```

The exact implementation may differ, but the core may depend only on this normalized contract.

### 9.3 Polling and event behavior

If the Rachio API does not provide a reliable push mechanism suitable for a custom integration, IrrigationOS will poll at a rate that balances state accuracy, cloud limits, and Home Assistant best practices.

Polling intervals may become temporarily faster during a pending command or active watering session, then return to a slower baseline.

### 9.4 Parallel validation

During development only:

- keep the official Home Assistant Rachio integration installed;
- compare controller and zone state;
- confirm discovery completeness;
- compare start/stop behavior;
- verify external activity detection;
- remove the dependency after validation.

Production IrrigationOS must not import, call, or require the official integration.

---

## 10. Canonical Data Model

### 10.1 Controller

```yaml
controller_id: buch_rachio
adapter_type: rachio
native_controller_id: "<opaque ID>"
display_name: Buch Rachio
location_id: home
capabilities:
  start_zone: true
  stop_all: true
  active_zone_status: true
  schedules: true
  rain_delay: true
```

### 10.2 Zone

```yaml
zone_id: front_yard_street
controller_id: buch_rachio
native_zone_id: "<opaque ID>"
display_name: Front Yard Street
enabled: true
plant_profile: mixed_shrubs
irrigation_method: drip
soil_profile: clay_loam
root_depth_mm: 450
application_rate_mm_h: null
flow_rate_l_min: null
slope_class: moderate
sun_exposure: full_sun
runoff_risk: moderate
control_enabled: false
```

### 10.3 Weather snapshot

```yaml
observed_at: "<timestamp>"
source: open_meteo
source_updated_at: "<timestamp>"
precipitation_observed_mm: 0.0
precipitation_forecast_24h_mm: 2.4
temperature_c: 27.1
relative_humidity_pct: 43
wind_speed_m_s: 2.8
solar_radiation_w_m2: 710
reference_et_mm: 4.9
confidence: moderate
```

### 10.4 Zone water-balance state

```yaml
zone_id: front_yard_street
as_of: "<timestamp>"
estimated_root_zone_water_mm: 31.2
field_capacity_mm: 42.0
management_allowed_depletion_mm: 16.8
current_depletion_mm: 10.8
soil_moisture_pct_of_available: 64
confidence: low
```

### 10.5 Recommendation

```yaml
recommendation_id: "<UUID>"
zone_id: front_yard_street
generated_at: "<timestamp>"
valid_until: "<timestamp>"
action: WATER
recommended_runtime_s: 900
cycle_plan:
  - run_s: 300
    soak_s: 1200
  - run_s: 300
    soak_s: 1200
  - run_s: 300
reason_codes:
  - ROOT_ZONE_BELOW_TARGET
  - NO_MEANINGFUL_RAIN_FORECAST
confidence: moderate
policy_version: "1.0.0"
input_snapshot_hash: "<hash>"
```

---

## 11. Weather Architecture

### 11.1 Default source

Open-Meteo is the default weather provider because it requires no API key and supports a low-friction installation.

### 11.2 Weather responsibilities

The weather subsystem should provide, where available:

- measured precipitation;
- forecast precipitation;
- temperature;
- humidity;
- wind;
- solar radiation or a suitable proxy;
- reference evapotranspiration;
- data timestamps;
- source health;
- confidence and fallback status.

### 11.3 Rain accounting

Rainfall must distinguish:

- observed rain;
- forecast rain;
- effective rain reaching the root zone;
- rain already accounted for;
- rain confidence;
- local sensor overrides.

Forecast rain may delay or reduce irrigation according to policy, but must not be treated identically to observed rain.

### 11.4 Stale weather behavior

If weather data becomes stale:

- Observation mode continues with a stale-data warning where safe;
- Simulation identifies the blocked condition;
- Live mode blocks new automatic runs when required weather inputs exceed the configured freshness limit;
- active watering is not necessarily stopped solely because weather refresh failed, unless another safety policy requires it.

---

## 12. Soil and Plant Modeling

### 12.1 Soil source

USDA SSURGO is the preferred initial recommendation source for US properties.

The recommendation is not treated as measured truth. It supplies a starting profile with an explicit confidence level.

### 12.2 Soil profile fields

Potential fields:

- texture class;
- available water capacity;
- infiltration rate;
- field capacity;
- wilting point;
- runoff tendency;
- effective root-zone depth constraints.

### 12.3 Plant profile fields

Potential fields:

- plant category;
- crop or landscape coefficient;
- root depth;
- allowed depletion;
- seasonal dormancy behavior;
- establishment status;
- stress tolerance.

### 12.4 Confidence model

Each modeled output carries a confidence level derived from the quality of inputs.

Example:

```text
High: measured local flow, measured rain, calibrated application rate
Moderate: reliable controller metadata and mapped soil
Low: default application rate and inferred landscape type
```

Confidence affects UI warnings and commissioning eligibility but does not silently modify the underlying facts.

---

## 13. Decision Engine

### 13.1 Inputs

The Decision Engine consumes an immutable input snapshot containing:

- zone configuration;
- soil profile;
- plant profile;
- recent irrigation history;
- observed rain;
- forecast rain;
- reference ET;
- seasonal factors;
- estimated root-zone state;
- watering restrictions;
- controller availability;
- active ownership state;
- policy version;
- current time and timezone.

### 13.2 Outputs

For each zone:

- `WATER`;
- `SKIP`;
- `DELAY`;
- `BLOCKED`;
- `NEEDS_CALIBRATION`.

Outputs include:

- runtime;
- cycle-and-soak plan;
- valid-until time;
- confidence;
- reason codes;
- full explanation;
- relevant input summary;
- policy version.

### 13.3 Determinism

Given the same normalized input snapshot and policy version, the engine must return the same recommendation.

This permits testing, replay, simulation, regression analysis, and Flight Recorder reconstruction.

### 13.4 Example explanation

> Backyard West remains above its target soil-water threshold. Measured rain contributed 5.3 mm yesterday, forecast rain probability is 78%, and today's estimated ET is 4.1 mm. Irrigation is skipped because the root zone is not yet depleted enough to justify watering.

---

## 14. Execution, Attribution, and Ownership

### 14.1 Command lifecycle

```text
Recommendation approved
        |
        v
Preflight safety validation
        |
        v
Command journal entry created
        |
        v
Ownership request: IRRIGATIONOS
        |
        v
Controller command issued
        |
        v
Acknowledgement observed
        |
        v
Active state monitored
        |
        v
Completion verified
        |
        v
Ownership released
```

### 14.2 External start

If a zone starts and there is no matching recent IrrigationOS command:

- classify the session as external;
- set owner to `EXTERNAL`;
- record the event;
- adopt actual controller state;
- do not immediately stop or reverse the session;
- continue safety monitoring;
- account for the delivered irrigation in the water balance after completion.

### 14.3 External stop

If an externally owned session stops:

- finalize observed runtime;
- update irrigation history;
- release `EXTERNAL` ownership;
- reevaluate future recommendations without automatically restarting the interrupted session unless policy explicitly permits it.

### 14.4 IrrigationOS command acknowledgement

A matching state transition within the acknowledgement window confirms command attribution.

No acknowledgement results in:

- command timeout;
- retry only when policy explicitly permits;
- ownership reconciliation;
- Flight Recorder error;
- issue or repair notification when persistent;
- no unbounded repeated commands.

### 14.5 Stop authority

`SAFETY` may stop any active session.

`EXTERNAL` activity normally outranks ordinary IrrigationOS intent, but does not outrank hard safety limits.

---

## 15. Safety Requirements

Mandatory safeguards:

1. Per-zone maximum runtime.
2. Controller-wide maximum continuous runtime.
3. No overlapping zone commands unless the controller explicitly supports and the policy permits them.
4. Emergency stop service.
5. Stale recommendation rejection.
6. Weather freshness gate.
7. Command acknowledgement timeout.
8. API retry limits.
9. External ownership detection.
10. Restart reconciliation.
11. Disabled-zone enforcement.
12. Watering-day and time-window enforcement.
13. Freeze protection when relevant.
14. Rain or rain-delay enforcement according to configured policy.
15. No automatic retry after an ambiguous state transition unless reconciled first.
16. No live action when controller identity or zone mapping is ambiguous.
17. Safe handling of Home Assistant shutdown or reload during an active session.

Optional future safeguards:

- leak detection from flow anomalies;
- broken-line detection;
- no-flow detection;
- excessive-flow shutoff;
- municipal restriction database;
- reservoir or well-level constraints.

---

## 16. Restart Recovery

On Home Assistant restart or integration reload, IrrigationOS must:

1. restore configuration and recent command-journal state;
2. query the controller before issuing any command;
3. detect whether irrigation is active;
4. attempt to match active state to an unexpired pending IrrigationOS command;
5. if no reliable match exists, conservatively assign `EXTERNAL` ownership;
6. restore or reconstruct runtime accounting;
7. refrain from replaying old start commands;
8. block new execution until reconciliation completes;
9. record the recovery outcome.

A restart must never cause a zone to start merely because an earlier recommendation existed.

---

## 17. Home Assistant Device and Entity Model

### 17.1 Devices

Create:

- one IrrigationOS system device per Config Entry;
- one controller device per physical irrigation controller;
- zone devices associated with the controller when this provides the clearest native HA experience.

### 17.2 Entity categories

#### System entities

Examples:

```text
sensor.irrigationos_mode
sensor.irrigationos_system_status
sensor.irrigationos_weather_status
sensor.irrigationos_last_decision_run
binary_sensor.irrigationos_live_control_ready
button.irrigationos_emergency_stop
```

#### Controller entities

Examples:

```text
binary_sensor.buch_rachio_online
sensor.buch_rachio_active_zone
sensor.buch_rachio_remaining_runtime
binary_sensor.buch_rachio_rain_delay
```

#### Zone entities

Examples:

```text
switch.front_yard_street_irrigation
sensor.front_yard_street_recommendation
sensor.front_yard_street_recommended_runtime
sensor.front_yard_street_estimated_soil_moisture
sensor.front_yard_street_last_watered
sensor.front_yard_street_next_recommended_watering
binary_sensor.front_yard_street_watering
```

Final entity naming must follow Home Assistant entity-platform conventions. IrrigationOS must not invent an unsupported custom entity domain solely for branding.

### 17.3 Entity semantics

The zone switch represents direct manual control through IrrigationOS, not the decision engine's recommendation.

Manual zone starts initiated through an IrrigationOS entity or service must be explicitly attributed and may be classified as an IrrigationOS manual command distinct from automatic execution.

### 17.4 Entity availability

Availability must reflect whether the specific data or control path is usable. A weather outage should not necessarily make all controller-control entities unavailable, and a controller outage should not erase previously calculated recommendations.

---

## 18. Home Assistant Services

Proposed services:

```text
irrigationos.start_zone
irrigationos.stop_controller
irrigationos.run_decision_cycle
irrigationos.recalculate_zone
irrigationos.enter_observation_mode
irrigationos.enter_simulation_mode
irrigationos.enable_live_mode
irrigationos.disable_live_mode
irrigationos.emergency_stop
irrigationos.acknowledge_external_session
irrigationos.export_flight_recorder
```

All control services must validate permissions, ownership, safety state, target identity, and duration limits.

Live-mode enablement should use Config/Options Flow confirmation rather than being trivially activated by an unaudited service call.

---

## 19. Diagnostics and Repairs

### 19.1 Diagnostics export

May include:

- integration version;
- Home Assistant version;
- redacted Config Entry metadata;
- controller capability summary;
- zone configuration without secrets;
- provider status;
- coordinator timestamps;
- recent normalized errors;
- recent recommendation summaries;
- ownership state;
- command-journal summaries with opaque identifiers redacted or hashed.

Must exclude:

- API keys;
- authorization headers;
- raw secrets;
- precise location unless explicitly required and suitably reduced/redacted;
- personal identity details not needed for troubleshooting.

### 19.2 Repair issues

Create Home Assistant Repairs issues for conditions such as:

- authentication failure;
- controller missing;
- previously mapped zone removed;
- weather source stale;
- location unavailable;
- live commissioning invalidated;
- repeated command acknowledgement failure;
- unresolved active state after restart;
- unsupported controller capability.

---

## 20. Flight Recorder

### 20.1 Event categories

Minimum events:

```text
SYSTEM_START
SYSTEM_STOP
CONFIG_CHANGED
MODE_CHANGED
PROVIDER_UPDATE
PROVIDER_ERROR
CONTROLLER_STATE_OBSERVED
ZONE_STATE_CHANGED
DECISION_STARTED
DECISION_COMPLETED
RECOMMENDATION_CREATED
RECOMMENDATION_BLOCKED
COMMAND_REGISTERED
COMMAND_SENT
COMMAND_ACKNOWLEDGED
COMMAND_TIMEOUT
COMMAND_FAILED
OWNER_CHANGE_REQUESTED
OWNER_CHANGED
OWNER_CHANGE_REJECTED
EXTERNAL_SESSION_STARTED
EXTERNAL_SESSION_COMPLETED
SAFETY_INTERLOCK_ACTIVATED
EMERGENCY_STOP
RESTART_RECONCILIATION
CALIBRATION_UPDATED
```

### 20.2 Record structure

Each record should contain:

- schema version;
- event ID;
- timestamp in UTC;
- local timestamp and timezone;
- event type;
- severity;
- Config Entry/controller/zone internal IDs;
- correlation ID;
- command or recommendation ID when applicable;
- normalized payload;
- prior-record hash and current-record hash in a later integrity-enabled implementation.

### 20.3 Retention

Retention must be configurable and bounded. Default retention should support meaningful troubleshooting without unbounded disk growth.

---

## 21. Repository Structure

```text
irrigationos/
├── custom_components/
│   └── irrigationos/
│       ├── __init__.py
│       ├── manifest.json
│       ├── const.py
│       ├── config_flow.py
│       ├── coordinator.py
│       ├── entity.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── switch.py
│       ├── button.py
│       ├── diagnostics.py
│       ├── repairs.py
│       ├── services.yaml
│       ├── strings.json
│       ├── translations/
│       │   └── en.json
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── rachio/
│       │       ├── __init__.py
│       │       ├── api.py
│       │       ├── adapter.py
│       │       ├── models.py
│       │       └── errors.py
│       ├── weather/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── open_meteo.py
│       ├── soil/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   └── ssurgo.py
│       ├── decision_engine/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── models.py
│       │   ├── policy.py
│       │   └── explanations.py
│       ├── execution/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── ownership.py
│       │   ├── command_journal.py
│       │   ├── safety.py
│       │   └── recovery.py
│       └── flight_recorder/
│           ├── __init__.py
│           ├── recorder.py
│           ├── models.py
│           └── retention.py
├── tests/
│   ├── components/irrigationos/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
│   ├── IRRIGATIONOS_ARCHITECTURE_V1.md
│   ├── COMMISSIONING.md
│   ├── SECURITY.md
│   └── DEVELOPMENT.md
├── hacs.json
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 22. Development Phases

### Phase 0 — Architecture and contracts

Deliverables:

- canonical architecture specification;
- normalized controller models;
- adapter interface;
- error taxonomy;
- entity model;
- security rules;
- test strategy.

Exit criterion:

- architecture reviewed and accepted.

### Phase 1 — Standalone Rachio foundation

Deliverables:

- HACS repository scaffold;
- manifest and Config Flow;
- API-key validation;
- account/controller/zone discovery;
- coordinator;
- controller and zone devices;
- read-only entities;
- redacted diagnostics;
- basic Flight Recorder;
- Observation mode.

Exit criterion:

- install IrrigationOS, enter API key, and discover the user's controller and four zones without relying on the official HA Rachio integration.

### Phase 2 — State, manual control, and attribution

Deliverables:

- normalized active watering state;
- bounded manual start/stop service;
- command journal;
- command acknowledgement;
- external activity detection;
- ownership manager;
- restart recovery;
- emergency stop;
- safety runtime limits.

Exit criterion:

- controlled test proves that an IrrigationOS command is correctly attributed, an external command is not misattributed, and restart recovery is conservative.

### Phase 3 — Weather and soil

Deliverables:

- Open-Meteo provider;
- weather freshness and confidence;
- rain accounting;
- SSURGO lookup;
- soil recommendations;
- per-zone soil overrides.

Exit criterion:

- each zone has a weather/soil input snapshot sufficient for observation calculations.

### Phase 4 — Decision Engine

Deliverables:

- ET and water-balance models;
- plant profiles;
- zone recommendations;
- reason codes;
- human-readable explanations;
- replayable input snapshots;
- recommendation entities.

Exit criterion:

- deterministic zone recommendations are produced in Observation mode and pass unit/regression tests.

### Phase 5 — Simulation and commissioning

Deliverables:

- Simulation mode;
- simulated execution plans;
- commissioning checklist;
- per-zone readiness;
- dashboard/Operations Center entities;
- validation reports.

Exit criterion:

- simulation passes for all intended live zones with no unresolved critical issue.

### Phase 6 — Staged live control

Deliverables:

- Live mode;
- one-zone pilot;
- cycle-and-soak execution;
- completion verification;
- live safety monitoring;
- staged expansion to additional zones.

Exit criterion:

- all selected zones operate safely with verified state, explanations, attribution, and recovery.

### Phase 7 — Optimization and additional adapters

Potential work:

- water-use estimation;
- measured flow support;
- leak detection;
- savings reports;
- municipal restrictions;
- premium weather providers;
- personal weather stations;
- additional controller adapters.

---

## 23. v1 Acceptance Criteria

The first installable v1 foundation is accepted when all of the following are true:

1. Installation through HACS succeeds.
2. Config Flow accepts a valid Rachio API key.
3. Invalid credentials produce a clear error and do not create a Config Entry.
4. The account identity is retrieved automatically.
5. The controller is discovered automatically.
6. All four current Rachio zones are discovered automatically.
7. No Rachio IDs must be entered manually.
8. No official Home Assistant Rachio integration is required.
9. IrrigationOS creates stable devices and read-only entities.
10. Controller and active-watering state refresh correctly.
11. Credentials are absent from logs and diagnostics.
12. Observation mode is the default.
13. No automatic watering command is possible in the initial observation-only milestone.
14. The Flight Recorder records setup, refresh, state, and error events.
15. Reload and Home Assistant restart do not duplicate devices or entities.
16. Tests cover authentication, discovery, normalization, redaction, setup, reload, and common API failures.
17. Home Assistant quality checks, formatting, typing, and tests pass in CI.

---

## 24. Initial User Installation Experience

Target experience:

```text
1. Open HACS.
2. Add the IrrigationOS repository.
3. Install IrrigationOS.
4. Add Integration -> IrrigationOS.
5. Paste the Rachio API key.
6. Confirm the discovered controller and zones.
7. Accept or edit location, weather, and soil recommendations.
8. Finish setup.
9. IrrigationOS begins in Observation mode.
```

No YAML, manual identity IDs, helper creation, or existing Rachio integration is required.

---

## 25. Current Installation Mapping

Initial known native Rachio zones:

```yaml
zones:
  - zone_id: avocado_tree
    current_reference_entity: switch.buch_rachio_avocado_tree

  - zone_id: backyard_west
    current_reference_entity: switch.buch_rachio_backyard_west

  - zone_id: east_perimeter_podocarpus
    current_reference_entity: switch.buch_rachio_east_perimeter_podocarpus

  - zone_id: front_yard_street
    current_reference_entity: switch.buch_rachio_front_yard_street
```

These current Home Assistant entities are validation references only. IrrigationOS will discover the underlying Rachio zones directly and create its own entities.

Existing `valve.*` helpers used for HomeKit presentation are explicitly excluded as sources of truth.

---

## 26. Security Requirements

- Store credentials only in the Home Assistant Config Entry.
- Never log request headers containing authorization.
- Redact API keys from exceptions and diagnostics.
- Use Home Assistant's asynchronous HTTP facilities and lifecycle management.
- Use HTTPS endpoints only.
- Bound retries and timeouts.
- Avoid storing raw cloud responses longer than needed.
- Treat controller and zone names as potentially user-identifying data in exported diagnostics.
- Document all external network services.
- Do not execute controller commands from unauthenticated external callbacks.

---

## 27. Testing Strategy

### Unit tests

- API-response normalization;
- model validation;
- weather calculations;
- soil mapping;
- decision determinism;
- reason-code generation;
- ownership priority;
- safety gates;
- command matching;
- redaction.

### Integration tests

- Config Flow;
- reauthentication;
- setup and unload;
- reload;
- coordinator failure and recovery;
- entity creation;
- duplicate prevention;
- service validation;
- restart reconciliation.

### Contract tests

Recorded, redacted Rachio API fixtures verify that adapter behavior remains stable when core code changes.

### Live commissioning tests

- discover all controllers and zones;
- compare states with the existing Rachio integration;
- start one zone for a short bounded duration;
- acknowledge state transition;
- stop the zone;
- detect an external Rachio-app start;
- detect external stop;
- restart Home Assistant during a controlled test and verify conservative recovery.

---

## 28. Open Decisions Deferred Beyond the Baseline

The following do not block Phase 1 but must be resolved before later phases:

1. Exact Open-Meteo endpoints and ET derivation strategy.
2. SSURGO query mechanism and caching policy.
3. Default observation duration before commissioning.
4. Whether one Config Entry may contain multiple controllers in the first release.
5. Exact Flight Recorder storage format and retention default.
6. Whether external sessions receive a maximum-duration warning or hard stop.
7. Municipal watering-restriction source and policy.
8. Default application-rate assumptions by irrigation type.
9. Home Assistant entity naming after testing against platform conventions.
10. Whether direct manual zone switches are included in the observation-only milestone or Phase 2.

---

## 29. Immediate Next Engineering Task

Create the repository scaffold and implement Phase 1 in this order:

1. Repository, `manifest.json`, HACS metadata, CI, and test scaffold.
2. Normalized controller models and adapter contract.
3. Rachio API client with secure key validation.
4. Config Flow.
5. Account, controller, and zone discovery.
6. Coordinator and read-only state refresh.
7. Home Assistant devices and entities.
8. Redacted diagnostics.
9. Basic Flight Recorder.
10. Reload/restart tests and CI validation.

The first proof milestone is:

> IrrigationOS installs through HACS, accepts the Rachio API key, discovers the Buch Rachio controller and all four zones, and presents their state in Home Assistant without requiring the existing Home Assistant Rachio integration.

---

## 30. Canonical Decision

This document establishes the approved v1 foundation:

- IrrigationOS is a standalone Home Assistant custom integration.
- It connects directly to Rachio.
- It owns authentication, discovery, entities, state, and commands.
- It begins in Observation mode.
- Its decision engine remains controller-independent.
- Its execution path is centralized, attributed, safety-gated, recoverable, and auditable.
- Weather and soil are native IrrigationOS subsystems with optional local enhancements.
- HomeKit helpers and other presentation entities are never sources of truth.

Changes to these foundational decisions should be recorded through a versioned architecture update or Architecture Decision Record rather than silently introduced in implementation.
