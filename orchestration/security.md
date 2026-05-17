# Security & Access Control

**Role 4 — Orchestration & Operations Engineer**
HPE GreenLake Digital Twin | Data Engineering Capstone

---

## 1. Guiding Principles

| Principle | Implementation |
|-----------|---------------|
| Least privilege | Each service only has the permissions it needs for its specific task |
| No hardcoded credentials | All AWS access via LabRole (instance profile / environment) |
| Encryption at rest | S3 SSE-S3 enabled on all zones; Athena query results encrypted |
| Encryption in transit | All API calls over HTTPS/TLS; Supabase connection over SSL |
| Credential isolation | `.env` file excluded via `.gitignore`; no secrets in source code |

---

## 2. IAM Role: LabRole

All AWS services in this project use **LabRole** — the pre-configured IAM role provided by AWS Academy. No custom IAM roles or users are created.

**Services that assume LabRole:**

| Service | How it assumes LabRole | Actions needed |
|---------|------------------------|----------------|
| AWS Glue ETL Jobs | Glue assumes LabRole as job execution role | `s3:GetObject`, `s3:PutObject`, `glue:*` |
| AWS Glue Crawler | Glue assumes LabRole | `s3:GetObject`, `s3:ListBucket`, `glue:*` |
| AWS Athena | Uses LabRole via console/CLI | `s3:GetObject`, `s3:PutObject` on `athena-results/` |
| AWS QuickSight | Configured to use LabRole | `athena:StartQueryExecution`, `s3:GetObject` |
| `run_pipeline.sh` | Reads credentials from environment (`~/.aws/credentials` or env vars set by Academy lab) | `glue:StartJobRun`, `glue:StartCrawler`, `athena:StartQueryExecution`, `s3:*` on project bucket |

**What we never do:**
- Store `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in source files
- Commit `.aws/credentials` or any `.env` file with real values
- Create IAM users for the project

---

## 3. S3 Bucket: `hpe-greenlake-dt-datalake`

### Zone Structure

```
s3://hpe-greenlake-dt-datalake/
├── raw/                    # Landing zone — original CSVs from Supabase
│   ├── telemetry_readings/
│   ├── incidents/
│   └── anomalies/
├── processed/              # Transformed — Parquet, schema-aligned
│   ├── telemetry/year=YYYY/vehicle_type=XXX/
│   ├── incidents/year=YYYY/
│   └── anomalies/year=YYYY/
├── curated/                # Aggregated views ready for QuickSight
│   └── kpi_summary/
├── data_quality/           # DQ reports (JSON, HTML)
│   └── report_YYYYMMDD.json
└── athena-results/         # Athena query output (auto-managed)
```

### Bucket Policy

The bucket is **not public**. The policy below restricts access to LabRole and denies all other principals:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowLabRoleOnly",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::<ACCOUNT_ID>:role/LabRole"
      },
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::hpe-greenlake-dt-datalake",
        "arn:aws:s3:::hpe-greenlake-dt-datalake/*"
      ]
    },
    {
      "Sid": "DenyAllOther",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": [
        "arn:aws:s3:::hpe-greenlake-dt-datalake",
        "arn:aws:s3:::hpe-greenlake-dt-datalake/*"
      ],
      "Condition": {
        "StringNotLike": {
          "aws:PrincipalArn": "arn:aws:iam::<ACCOUNT_ID>:role/LabRole"
        }
      }
    }
  ]
}
```

> Replace `<ACCOUNT_ID>` with the AWS Academy account ID before applying.

### Bucket Configuration

| Setting | Value | Reason |
|---------|-------|--------|
| Block all public access | ON | No data should be publicly accessible |
| Versioning | OFF | Cost control in Academy lab environment |
| Server-side encryption | SSE-S3 (AES-256) | Data at rest encrypted without KMS cost |
| Transfer acceleration | OFF | Not needed for this workload |

---

## 4. Glue Resources

### Glue Data Catalog

The Glue Data Catalog is accessible only to LabRole. The database `digital_twin_db` contains tables for:
- `telemetry_readings_parquet`
- `incidents_parquet`
- `anomalies_parquet`

No resource-based policies are applied to the catalog beyond LabRole's built-in permissions.

### Glue Jobs

| Job | Description | Max DPUs | Timeout |
|-----|-------------|----------|---------|
| `dt-transform-csv-to-parquet` | Reads raw CSVs, aligns schemas, writes Parquet | 2 | 30 min |
| `dt-data-quality-check` | Runs 8+ DQ rules, writes JSON report to S3 | 2 | 20 min |

Jobs are defined with `--TempDir s3://hpe-greenlake-dt-datalake/glue-temp/` and use LabRole.

---

## 5. Athena

- Query results are written to `s3://hpe-greenlake-dt-datalake/athena-results/`
- Results are accessible only to LabRole
- Workgroup: `primary` (default Academy workgroup)
- No saved queries contain credentials or sensitive values

---

## 6. Supabase (Source Database)

Supabase credentials (URL + anon key) are stored in `.env` and **never committed**.

```
# .env (NOT committed — listed in .gitignore)
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
```

The ingestion script (`pipeline/ingest.py`) reads from environment variables only:
```python
import os
url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
```

The Supabase service role key has read-only scope for the tables:
`telemetry_readings`, `incidents`, `anomalies`.

---

## 7. .gitignore Rules (Security Relevant)

The following patterns are enforced in `.gitignore` to prevent accidental credential commits:

```
# Environment files
.env
.env.local
.env.*.local

# AWS credentials
.aws/
aws-credentials.json

# Supabase keys
supabase/.env

# Data files (prevent full dataset commits)
*.csv
*.parquet
data_samples/*.csv
!data_samples/README.md
```

---

## 8. Presentation Day — Backup Plan

If the AWS Academy lab environment is unavailable on presentation day, the fallback is a local Docker + PySpark demo:

1. Start local PySpark container: `docker compose -f orchestration/docker-compose-local.yml up`
2. Run local pipeline: `python3 pipeline/local_pipeline.py --input data_samples/ --output /tmp/output/`
3. Inspect Parquet output: `python3 -c "import pandas as pd; print(pd.read_parquet('/tmp/output/telemetry/'))"`

The local demo covers: ingestion from CSV samples, CSV → Parquet transformation, DQ rule execution, and sample Athena-equivalent queries via DuckDB.

---

## 9. Access Control Summary

| Resource | Who can access | How |
|----------|---------------|-----|
| S3 raw zone | LabRole only | Bucket policy |
| S3 processed zone | LabRole only | Bucket policy |
| S3 curated zone | LabRole + QuickSight | Bucket policy |
| Glue Data Catalog | LabRole only | IAM |
| Athena queries | LabRole only | IAM |
| QuickSight dashboards | Team members via Academy console | QuickSight user permissions |
| Supabase source DB | Ingestion script via service key | .env (not committed) |
