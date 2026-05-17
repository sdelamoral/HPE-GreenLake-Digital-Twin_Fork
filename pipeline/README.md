# Pipeline — Role 1

**Role:** Data Engineer
**Owner:** [Nombre]

## Responsibilities

- Export raw data from Supabase to `s3://.../raw/` (CSV)
- Run AWS Glue ETL Job to convert CSV → Parquet with schema alignment
- Configure Glue Crawler and Data Catalog
- Resolve schema differences between `telemetry_readings`, `incidents`, and `anomalies`

## Deliverables (to be added here)

- `ingest.py` — Supabase export script
- `glue_etl_job.py` — Glue ETL transformation script
- Data flow diagram

## Schema Alignment Decisions

| Source column | Processed column | Notes |
|---------------|-----------------|-------|
| `timestamp` (telemetry) | `event_timestamp` | Unified temporal field |
| `reported_at` (incidents) | `event_timestamp` | Renamed for consistency |
| `assigned_vehicle_ids` (UUID[]) | `assigned_vehicle_ids` (STRING) | Array serialized as JSON string |

See `docs/technical_decisions.md` ADR-05 for rationale.
