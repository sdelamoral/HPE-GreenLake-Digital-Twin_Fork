# Data Quality — Role 2

**Role:** Data Quality Engineer
**Owner:** [Nombre]

## Responsibilities

- Profile the dataset: volume, types, distributions, null rates
- Define and implement 10 DQ rules (see `rules.md`)
- Generate an executable report with pass/fail per rule

## Tool

**AWS Glue Data Quality** (primary) + **Pandera** (local/backup demo)

## Deliverables (to be added here)

- `validate.py` — Glue/Pandera validation script
- `rules.md` — All 10 rules with business justification
- `report_YYYYMMDD.json` / `report.html` — Executed results

## Rules Overview

| ID | Category | Rule |
|----|----------|------|
| DQ-01 | Completeness | `vehicle_id` not null in telemetry and anomalies |
| DQ-02 | Validity | `metric_type` in allowed set |
| DQ-03 | Range | Telemetry `value` within plausible range per metric |
| DQ-04 | Temporal | `event_timestamp` not null and not in the future |
| DQ-05 | Validity | `incident_type` in allowed set |
| DQ-06 | Consistency | `resolved_at` ≥ `reported_at` when not null |
| DQ-07 | Uniqueness | No duplicate `(vehicle_id, metric_type, event_timestamp)` in telemetry |
| DQ-08 | Validity | `severity` only `info`, `warning`, `critical` |
| DQ-09 | Format | `latitude` ∈ [−90, 90], `longitude` ∈ [−180, 180] |
| DQ-10 | Consistency | Anomaly `status=resolved` only if `resolved_at` is not null |

Full justifications in `rules.md`.
