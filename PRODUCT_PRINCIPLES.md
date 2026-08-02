# IrrigationOS Product Principles

1. **Observe before controlling.** Every new controller capability begins in Observation mode. No release gains live authority implicitly.
2. **Identity belongs to IrrigationOS.** Controller names, provider IDs, and Home Assistant entity IDs are replaceable bindings, not domain identity.
3. **A physical slot is permanent.** Controller capacity defines stable numbered slots. A slot keeps its identity when a vendor zone is renamed, disabled, removed, or replaced.
4. **Unknown is not idle.** Missing or failed observations remain explicit and cannot be interpreted as a confirmed safe state.
5. **Partial truth is useful when labeled.** A secondary endpoint failure does not discard a safe base snapshot; its source, timestamp, quality, and error remain visible.
6. **Names are presentation.** Default entity names follow stable physical slots such as Zone 1. Users and vendors may rename landscapes without changing identity.
7. **Vendor details stop at the adapter.** Higher layers consume canonical models and explicit provider bindings.
8. **Safety authority stays centralized.** Future execution must pass ownership, policy, attribution, and runtime safety gates.
9. **Explainability is a product feature.** Material observations and future decisions must be traceable without exposing credentials or private identifiers.
10. **Migration is part of correctness.** Model improvements preserve existing registry identity and user-authored landscape data whenever possible.
