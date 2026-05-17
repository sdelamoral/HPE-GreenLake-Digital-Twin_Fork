# Data Samples

This folder contains **small samples only** (max ~100 rows per file) for testing and demonstration purposes.

**DO NOT commit full datasets here.** Full datasets stay in S3 only.
Committing a full dataset results in a −10 penalty per the project rules.

## Files

- `telemetry_sample.csv` — 100 rows from `telemetry_readings` (to be added by Role 1)
- `incidents_sample.csv` — 50 rows from `incidents` (to be added by Role 1)
- `anomalies_sample.csv` — 50 rows from `anomalies` (to be added by Role 1)

These samples are used by:
- `pipeline/local_pipeline.py` — local backup demo
- `data_quality/validate.py` — local DQ test run
- `analytics/local_query.py` — local DuckDB queries

## How to generate samples

```bash
python3 pipeline/ingest.py \
  --tables telemetry_readings incidents anomalies \
  --limit 100 \
  --output data_samples/
```
