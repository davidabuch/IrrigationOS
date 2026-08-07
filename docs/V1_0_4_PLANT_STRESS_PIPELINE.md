# v1.0.4 — Plant Stress Pipeline Integration

IrrigationOS now carries v1.0.3 Water Requirement results into the existing Plant Stress engines inside the synchronized Home Assistant pipeline.

## Delivered

- Deterministic current-condition Environmental Intelligence derived from the selected Home Assistant weather entity.
- Heat, freeze, and wind exposure signals with explicit evidence references and provenance.
- Per-area water-deficit, heat, and freeze stress assessments using the existing domain engines.
- Aggregate Plant Stress assessments that preserve independent dimensions and provenance.
- Explicit partial or blocked states when required drying, forecast, or plant-knowledge evidence is unavailable.

## Safety boundary

This release remains observation and simulation only. It does not start, stop, reschedule, or otherwise actuate irrigation hardware.

Current Home Assistant weather provides point-in-time temperature and wind context but does not by itself provide the precipitation/ET history required for a complete drying-trend signal. Water-deficit stress therefore remains explicitly partial or unavailable until that evidence is integrated rather than treating missing values as zero.
