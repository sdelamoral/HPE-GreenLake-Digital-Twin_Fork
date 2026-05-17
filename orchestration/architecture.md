# Architecture Diagram

**Role 4 — Orchestration & Operations Engineer**
HPE GreenLake Digital Twin | Data Engineering Capstone

> This file contains the Mermaid source for the architecture diagram.
> To export as PNG: paste the code block into [mermaid.live](https://mermaid.live) → Download PNG → save as `architecture.png` in this folder.

---

## Full Pipeline Architecture

```mermaid
flowchart TD
    %% ── DATA SOURCES ──────────────────────────────────────────
    subgraph SRC["DATA SOURCES (Supabase / PostgreSQL)"]
        T["📡 telemetry_readings\n9 metrics · 18 vehicles · ~5 s/tick\nSchema A: vehicle_id, metric_type, value, unit, lat, lng, timestamp"]
        I["🚨 incidents\nSchema B: title, incident_type, severity,\nlat, lng, status, assigned_vehicle_ids, reported_at"]
        A["⚠️ anomalies\nSchema C: vehicle_id, metric_type,\nactual_value, severity, status, timestamp"]
    end

    %% ── INGESTION ─────────────────────────────────────────────
    subgraph INGEST["STAGE 1 — INGEST (pipeline/ingest.py)"]
        PY["Python 3 + supabase-py\nExports tables as CSV\nPartial loads by timestamp"]
    end

    %% ── S3 RAW ───────────────────────────────────────────────
    subgraph RAW["S3 RAW ZONE"]
        R1["s3://.../raw/telemetry_readings/"]
        R2["s3://.../raw/incidents/"]
        R3["s3://.../raw/anomalies/"]
    end

    %% ── TRANSFORM ────────────────────────────────────────────
    subgraph TRANSFORM["STAGE 2 — TRANSFORM (Glue ETL Job)"]
        G1["dt-transform-csv-to-parquet\n• Align schemas (rename / cast columns)\n• Convert CSV → Parquet (Snappy)\n• Add partition columns: year, vehicle_type\n• Drop PII columns (profile data)"]
    end

    %% ── S3 PROCESSED ─────────────────────────────────────────
    subgraph PROC["S3 PROCESSED ZONE"]
        P1["s3://.../processed/telemetry/\nyear=YYYY/vehicle_type=XXX/*.parquet"]
        P2["s3://.../processed/incidents/\nyear=YYYY/*.parquet"]
        P3["s3://.../processed/anomalies/\nyear=YYYY/*.parquet"]
    end

    %% ── DATA QUALITY ─────────────────────────────────────────
    subgraph DQ["STAGE 4 — DATA QUALITY (Glue DQ Job)"]
        DQJ["dt-data-quality-check\n8+ rules: completeness, range validity,\nreferential integrity, temporal validity,\nformat, uniqueness, consistency"]
        DQR["DQ Report → s3://.../data_quality/\nreport_YYYYMMDD.json"]
    end

    %% ── CATALOG ──────────────────────────────────────────────
    subgraph CAT["STAGE 3 — CATALOG (Glue Crawler)"]
        CR["dt-crawler-processed\nScans processed/ zone\nUpdates Glue Data Catalog"]
        GDC["Glue Data Catalog\ndatabase: digital_twin_db\ntables: telemetry · incidents · anomalies"]
    end

    %% ── QUERY ────────────────────────────────────────────────
    subgraph QUERY["STAGE 5 — QUERY (Athena)"]
        ATH["Amazon Athena\n5+ views · 3-query benchmark\nCSV vs Parquet+partition"]
        ATH_OUT["s3://.../athena-results/"]
    end

    %% ── CURATED ──────────────────────────────────────────────
    subgraph CUR["S3 CURATED ZONE"]
        C1["s3://.../curated/kpi_summary/\nPre-aggregated KPIs for QuickSight"]
    end

    %% ── VISUALIZE ────────────────────────────────────────────
    subgraph VIZ["STAGE 6 — VISUALIZE (QuickSight)"]
        QS["Amazon QuickSight\n4+ visualizations:\n• Vehicle health heatmap\n• Incident hotspot map\n• Anomaly trend by metric type\n• Maintenance risk by vehicle type"]
    end

    %% ── ORCHESTRATION ────────────────────────────────────────
    subgraph ORCH["ORCHESTRATION — run_pipeline.sh"]
        PIPE["Master bash script\nStage sequencing · Error handling\nPer-stage logging · Dry-run mode"]
    end

    %% ── SECURITY ─────────────────────────────────────────────
    subgraph SEC["SECURITY — LabRole · Bucket Policies · No Exposed Creds"]
        IAM["LabRole\n(assumed by all AWS services)"]
        BP["Bucket Policy\nDeny all except LabRole"]
        ENV[".env not committed\n.gitignore enforced"]
    end

    %% ── FLOWS ────────────────────────────────────────────────
    T & I & A --> PY
    PY --> R1 & R2 & R3
    R1 & R2 & R3 --> G1
    G1 --> P1 & P2 & P3
    P1 & P2 & P3 --> DQJ
    DQJ --> DQR
    P1 & P2 & P3 --> CR
    CR --> GDC
    GDC --> ATH
    ATH --> ATH_OUT
    ATH --> C1
    C1 --> QS

    PIPE -.->|orchestrates| PY
    PIPE -.->|orchestrates| G1
    PIPE -.->|orchestrates| CR
    PIPE -.->|orchestrates| DQJ
    PIPE -.->|orchestrates| ATH

    IAM -.->|assumed by| G1 & CR & ATH & DQJ
    BP -.->|protects| RAW & PROC & CUR

    %% ── STYLES ───────────────────────────────────────────────
    classDef source    fill:#1a3a5c,color:#fff,stroke:#4a9fd4
    classDef zone      fill:#0f2d4a,color:#cde,stroke:#2a6fa8
    classDef aws       fill:#1d6fa4,color:#fff,stroke:#4a9fd4
    classDef orch      fill:#b45309,color:#fff,stroke:#d97706
    classDef security  fill:#4a1d6a,color:#fff,stroke:#9333ea
    classDef dq        fill:#065f46,color:#fff,stroke:#10b981

    class T,I,A source
    class R1,R2,R3,P1,P2,P3,C1,ATH_OUT zone
    class G1,CR,GDC,ATH,QS,DQJ,DQR aws
    class PIPE,ORCH orch
    class IAM,BP,ENV,SEC security
    class DQ dq
```

---

## IAM / Access Control Layer

```mermaid
flowchart LR
    LAB["LabRole\n(AWS Academy)"]
    LAB -->|Execute| GLUE["AWS Glue\nJobs + Crawlers"]
    LAB -->|Query| ATHENA["Amazon Athena"]
    LAB -->|Read/Write| S3["S3 Bucket\nhpe-greenlake-dt-datalake"]
    LAB -->|Visualize| QS2["Amazon QuickSight"]

    BUCKET_POLICY["Bucket Policy\nDeny all ≠ LabRole"] -.->|enforces| S3

    DEV["Developer\n(Academy console)"]
    DEV -->|assumes| LAB
```

---

## Error Handling per Stage

| Stage | Failure condition | `run_pipeline.sh` response |
|-------|------------------|---------------------------|
| 1 — Ingest | No files in S3 after export | `die()` — pipeline stops, error logged |
| 2 — Transform | Glue job `FAILED` / `TIMEOUT` | `die()` with Glue error message |
| 3 — Catalog | Crawler stuck / not found | `die()` if not found; `warn()` if non-SUCCEEDED status |
| 4 — Quality | DQ job fails OR rules fail | `die()` — blocks downstream stages |
| 5 — Athena | Individual view fails | `warn()` — pipeline continues, failure noted in log |

All stages write timestamped entries to `orchestration/logs/pipeline_run_<ts>.log`.
