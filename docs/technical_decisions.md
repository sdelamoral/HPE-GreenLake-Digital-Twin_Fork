# Technical Decisions (ADRs)

**HPE GreenLake Digital Twin | Data Engineering Capstone — Path B**

Architecture Decision Records — short justifications for each non-obvious choice made during the project.

---

## ADR-01 — Storage Format: Parquet over CSV

**Decision:** Store processed data in Parquet (Snappy compression), not CSV or JSON.

**Alternatives considered:** CSV (original format), JSON (Supabase output), ORC.

**Rationale:**
- Parquet is columnar: queries that touch only a few columns (e.g., `value` + `timestamp`) scan only those columns, not full rows.
- Snappy compression reduces storage ~60–75% versus raw CSV for our numeric-heavy telemetry data.
- Athena charges per byte scanned — Parquet + partitioning directly reduces cost.
- Glue ETL has native Parquet read/write support; no extra libraries needed.
- ORC was considered but Parquet has broader ecosystem support (Pandas, Spark, DuckDB for backup demo).

**Benchmark target:** ≥ 80% scan size reduction on Q1 (total telemetry value by year).

---

## ADR-02 — Partitioning Strategy: year + vehicle_type for telemetry

**Decision:** Partition `processed/telemetry/` by `year=YYYY/vehicle_type=XXX/`.

**Alternatives considered:** Partition by `metric_type`, by `month`, by `vehicle_id`, no partitioning.

**Rationale:**
- Most dashboard queries filter by vehicle type (compare police vs ambulance health). Partitioning by `vehicle_type` prunes up to 80% of data for type-specific queries.
- `year` partitioning prevents full scans when querying recent data; telemetry accumulates indefinitely.
- `metric_type` partitioning was rejected: 9 partition values creates many small files, harming Athena performance.
- `vehicle_id` partitioning (18 values) creates too many small files.
- For `incidents` and `anomalies`, only `year` partitioning is used — smaller volumes don't justify a second partition column.

---

## ADR-03 — Orchestration: Bash master script over Step Functions / Glue Workflows

**Decision:** Use `orchestration/run_pipeline.sh` (bash + AWS CLI) as the primary orchestrator.

**Alternatives considered:** AWS Step Functions, AWS Glue Workflows.

**Rationale:**
- AWS Academy labs have session timeouts (4 hours). Step Functions state machines require persistent IAM roles and may incur costs that exceed lab credits.
- Glue Workflows require all jobs to be pre-created in the console before the workflow can be defined — adds setup friction for a team project.
- The bash script is self-contained, version-controlled, readable, and reproducible on any machine with AWS CLI. It covers all required orchestration behaviors: stage sequencing, wait loops, error handling, logging, and dry-run mode.
- The script is written to be easily replaced with Step Functions JSON if the team upgrades later.

**Trade-off:** No visual workflow UI. Mitigated by structured logging and the `--stage` flag for partial re-runs.

---

## ADR-04 — Data Quality Tool: Glue Data Quality (with Pandera fallback)

**Decision:** Use AWS Glue Data Quality for the primary DQ pipeline. Pandera is used for the local/backup demo.

**Alternatives considered:** Great Expectations, Pandera only, pandas asserts.

**Rationale:**
- Glue Data Quality integrates natively with Glue Jobs — no extra infrastructure, no separate server.
- Results are written to S3 as structured JSON, enabling automated pass/fail checking in `run_pipeline.sh`.
- Great Expectations requires a dedicated store (S3 or local) and more complex setup than our timeline allows.
- Pandera is used for the local backup demo (Docker + PySpark) because it runs without AWS.
- pandas asserts were rejected: no structured report output, hard to audit.

---

## ADR-05 — Schema Alignment: Unified timestamp column

**Decision:** Rename all temporal columns to `event_timestamp` in the processed zone.

**Alternatives considered:** Keep original names (`timestamp`, `reported_at`), use `created_at`.

**Rationale:**
- `telemetry_readings` uses `timestamp`, `incidents` uses `reported_at`, `anomalies` uses `timestamp`.
- Keeping different names makes cross-table Athena views verbose and error-prone.
- `event_timestamp` is semantically accurate for all three (it's when the event occurred, not when it was created).
- `created_at` exists in all three tables but represents DB insertion time — not analytically useful.

---

## ADR-06 — Exclude `profiles` table from the pipeline

**Decision:** Do not ingest the `profiles` table (user accounts) into the data lake.

**Rationale:**
- `profiles` contains emails and user roles — personal information not relevant to fleet analytics.
- Excluding it avoids any data privacy concerns (even though this is a simulated system).
- The pipeline's business questions (vehicle health, incident patterns, anomaly trends) do not require user identity data.

---

## ADR-07 — GPS data retained in processed zone

**Decision:** Keep `latitude`/`longitude` columns in the processed Parquet files.

**Alternatives considered:** Drop GPS columns, hash coordinates.

**Rationale:**
- All coordinates in this dataset are **simulated** — they represent fictional vehicle positions in Madrid, not real people's locations.
- Geographic coordinates are essential for the QuickSight incident hotspot map (Concept 6).
- No real personal data is exposed by retaining them.

---

## ADR-08 — S3 bucket name: `hpe-greenlake-dt-datalake`

**Decision:** Use a single bucket with path-based zone separation (raw/, processed/, curated/).

**Alternatives considered:** Separate buckets per zone, single bucket with no prefixes.

**Rationale:**
- AWS Academy labs have limited account permissions; creating multiple buckets may hit service limits.
- A single bucket with a clear prefix structure is simpler to manage and easier to apply a single bucket policy.
- Path-based zones are equivalent to separate buckets for access control purposes (prefix-level IAM conditions can be added if needed).
