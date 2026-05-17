# Orchestration — Role 4

**Role:** Orchestration & Operations Engineer
**Owner:** [Tu nombre]
**Project:** HPE GreenLake Digital Twin | AWS Data Engineering Capstone (Path B)

---

## Responsibilities

- Orchestrate the complete pipeline reproducibly via `run_pipeline.sh`
- Implement error handling for each stage (stop-on-failure with descriptive messages)
- Define and document access control (IAM, bucket policies) — see `security.md`
- Coordinate the final live demo and maintain a backup plan

---

## Files

| File | Description |
|------|-------------|
| `run_pipeline.sh` | Master bash script — runs all 5 stages in order via AWS CLI |
| `architecture.md` | Full pipeline architecture diagram (Mermaid source → export to `architecture.png`) |
| `security.md` | IAM roles, S3 bucket policies, credential management decisions |
| `logs/` | Timestamped run logs (auto-generated, not committed) |

---

## How to Run the Pipeline

### Prerequisites

1. AWS Academy lab must be active (LabRole credentials available)
2. AWS CLI installed (`aws --version`)
3. Python 3 installed with `pip install supabase boto3`
4. Copy `.env.example` → `.env` and fill in Supabase credentials

### Full pipeline (all stages)

```bash
cd /path/to/HPE-GreenLake-Digital-Twin_Fork
./orchestration/run_pipeline.sh
```

### Dry run (shows commands without executing)

```bash
./orchestration/run_pipeline.sh --dry-run
```

### Run a single stage

```bash
./orchestration/run_pipeline.sh --stage ingest
./orchestration/run_pipeline.sh --stage transform
./orchestration/run_pipeline.sh --stage catalog
./orchestration/run_pipeline.sh --stage quality
./orchestration/run_pipeline.sh --stage athena
```

### Environment variables (override defaults)

```bash
S3_BUCKET=my-bucket AWS_REGION=us-west-2 ./orchestration/run_pipeline.sh
```

---

## Stage Summary

| # | Stage | Tool | Input | Output |
|---|-------|------|-------|--------|
| 1 | Ingest | Python + supabase-py | Supabase tables | `s3://.../raw/*.csv` |
| 2 | Transform | AWS Glue ETL Job | `raw/*.csv` | `processed/*.parquet` |
| 3 | Catalog | AWS Glue Crawler | `processed/` | Glue Data Catalog |
| 4 | Quality | AWS Glue DQ Job | `processed/` | `data_quality/report_*.json` |
| 5 | Athena Views | Amazon Athena | Glue Catalog | Views in `digital_twin_db` |

---

## Error Handling

Each stage fails fast (`set -euo pipefail`) and logs the error before exiting.
To resume from a specific stage after fixing a failure:

```bash
./orchestration/run_pipeline.sh --stage transform   # skip ingest, start here
```

Logs are saved to `orchestration/logs/pipeline_run_<YYYYMMDD_HHMMSS>.log`.

---

## Backup Demo Plan

If the AWS Academy lab is unavailable on presentation day:

```bash
# 1. Start local PySpark environment
docker compose -f orchestration/docker-compose-local.yml up -d

# 2. Run local pipeline against sample data
python3 pipeline/local_pipeline.py --input data_samples/ --output /tmp/output/

# 3. Inspect results
python3 -c "import pandas as pd; print(pd.read_parquet('/tmp/output/telemetry/'))"

# 4. Run DQ rules locally
python3 data_quality/validate.py --input /tmp/output/

# 5. Query with DuckDB (Athena equivalent)
python3 analytics/local_query.py --input /tmp/output/
```

This covers: ingestion, transformation (CSV → Parquet), data quality, and analytics — all running locally on sample data from `data_samples/`.
