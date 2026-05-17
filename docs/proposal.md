# Path B Proposal — HPE GreenLake Digital Twin

**Course:** AWS Academy Data Engineering
**Team:** [Nombre del equipo]
**Members:**
- [Nombre 1] — Role 1: Data Engineer
- [Nombre 2] — Role 2: Data Quality Engineer
- [Nombre 3] — Role 3: Analytics Engineer
- [Nombre 4] — Role 4: Orchestration & Operations Engineer

**Submission date:** Week 1

---

## 1. Project Description

We propose to use the **HPE GreenLake Digital Twin for Emergency Vehicle Fleets** as our Path B dataset. This is an active project that simulates a fleet of 18 emergency vehicles (police, ambulance, fire truck, civil protection) operating in Madrid. A Node.js simulation engine generates 9 telemetry variables per vehicle every 5 seconds, manages incident lifecycles, runs anomaly detection, and feeds a Python LSTM model for predictive maintenance.

The project generates data continuously in a Supabase (PostgreSQL) database. We will extract three tables with different schemas, ingest them into an AWS S3 data lake, and build the full pipeline required by the capstone.

---

## 2. Data Sources

The dataset has **three sources with different schemas**, stored in Supabase:

### Source 1 — `telemetry_readings`

Real-time telemetry from 18 vehicles × 9 metric types × one reading every 5 seconds.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| vehicle_id | UUID | FK to vehicles |
| metric_type | TEXT | `engine_temp`, `fuel_level`, `speed`, `rpm`, `battery_voltage`, `oil_pressure`, `tire_pressure`, `mileage`, `coolant_temp` |
| value | NUMERIC | Sensor reading |
| unit | TEXT | `°C`, `%`, `km/h`, `RPM`, `V`, `bar`, `PSI`, `km` |
| latitude | NUMERIC | GPS latitude |
| longitude | NUMERIC | GPS longitude |
| timestamp | TIMESTAMPTZ | Reading timestamp |

**Estimated volume:** 18 vehicles × 9 metrics × 12 readings/min × 60 × 24 × 30 days ≈ **8.4 million rows/month**. A 30-day export comfortably exceeds the 500K row requirement.

### Source 2 — `incidents`

Emergency incidents managed by the simulation. Different schema from telemetry.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | TEXT | Incident title |
| description | TEXT | Details |
| incident_type | TEXT | `fire`, `medical`, `crime`, `accident`, `natural_disaster` |
| severity | TEXT | `info`, `warning`, `critical` |
| latitude | NUMERIC | Incident location |
| longitude | NUMERIC | Incident location |
| status | TEXT | `reported`, `dispatched`, `in_progress`, `resolved` |
| assigned_vehicle_ids | UUID[] | Array of dispatched vehicles |
| reported_at | TIMESTAMPTZ | Creation time |
| resolved_at | TIMESTAMPTZ | Resolution time (nullable) |

### Source 3 — `anomalies`

Threshold breach anomalies detected by the rule engine. Third distinct schema.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| vehicle_id | UUID | FK to vehicles |
| telemetry_reading_id | UUID | FK to telemetry |
| anomaly_type | TEXT | `threshold_breach` |
| metric_type | TEXT | Which sensor triggered it |
| expected_range | JSONB | `{min, max}` thresholds |
| actual_value | NUMERIC | Value that triggered the anomaly |
| severity | TEXT | `info`, `warning`, `critical` |
| status | TEXT | `active`, `acknowledged`, `resolved` |
| description | TEXT | Human-readable message |
| timestamp | TIMESTAMPTZ | Detection time |
| resolved_at | TIMESTAMPTZ | Nullable |

**Schema integration challenge:** The three tables have different primary concepts (sensor readings, geographic events, rule violations), different temporal fields (`timestamp` vs `reported_at`), and incompatible representations of `vehicle_id` (UUID FK in telemetry/anomalies vs UUID[] array in incidents). Aligning them into a unified Parquet schema is the Role 1 challenge.

---

## 3. Mapping of the 7 Mandatory Concepts

### Concept 1 — Data Lake on S3 (clear raw / processed / curated zones)

We will create three zones in S3 bucket `hpe-greenlake-dt-datalake`:
- **raw/**: CSV exports from Supabase, one prefix per table
- **processed/**: Parquet files with aligned schemas and partition columns
- **curated/**: Pre-aggregated KPI tables ready for QuickSight

### Concept 2 — Schema-on-read (Glue Crawler + Athena)

A Glue Crawler will scan `processed/` and register tables in the Glue Data Catalog (`digital_twin_db`). Athena will query the Parquet files directly — no data movement, no loading.

### Concept 3 — Physical Optimization (Parquet + partitioning + benchmark)

Telemetry will be partitioned by `year` and `vehicle_type` (5 types × years). Incidents and anomalies by `year`. We will benchmark 3 queries comparing CSV vs Parquet+partition to measure scan size and time reduction.

### Concept 4 — Data Quality (8+ rules)

Using **Glue Data Quality** or **Pandera**, we will enforce:
1. `vehicle_id` not null in telemetry and anomalies
2. `metric_type` in allowed set (`engine_temp`, `fuel_level`, ...)
3. Telemetry `value` within plausible range per metric type (e.g., `engine_temp` ∈ [−20, 150])
4. `timestamp` not null and not in the future
5. `incident_type` in allowed set (`fire`, `medical`, ...)
6. Incidents: `resolved_at` ≥ `reported_at` when not null
7. No duplicate `(vehicle_id, metric_type, timestamp)` in telemetry
8. Anomalies `severity` only one of `info`, `warning`, `critical`
9. Telemetry `latitude` ∈ [−90, 90] and `longitude` ∈ [−180, 180]
10. `status` field consistency (anomaly `resolved` only if `resolved_at` is not null)

### Concept 5 — Orchestration (run_pipeline.sh)

A master bash script (`orchestration/run_pipeline.sh`) runs all stages in order via AWS CLI with per-stage error handling and logging.

### Concept 6 — Visualization (QuickSight dashboard)

Four visualizations answering operational questions:
1. **Vehicle health heatmap** — risk score by vehicle type over time
2. **Incident hotspot map** — geographic density of incidents by type
3. **Anomaly trend** — count by metric_type and severity per week
4. **Response time analysis** — `resolved_at − reported_at` distribution by incident_type

### Concept 7 — Security (LabRole, no exposed credentials, restricted buckets)

LabRole assumed by all AWS services. S3 bucket policy denies all principals except LabRole. Supabase credentials in `.env` (not committed). `.gitignore` enforces no secrets in repository.

---

## 4. Proposed Architecture

```
Supabase (PostgreSQL)
  ├── telemetry_readings  ──┐
  ├── incidents            ─┼──► Python ingest.py ──► S3 raw/  (CSV)
  └── anomalies            ─┘
                                          │
                                          ▼
                              AWS Glue ETL Job (CSV → Parquet, schema alignment)
                                          │
                                          ▼
                              S3 processed/  (Parquet, partitioned)
                                    │              │
                                    ▼              ▼
                            Glue Crawler    Glue DQ Job (8+ rules)
                                    │              │
                                    ▼              ▼
                          Glue Data Catalog    DQ Report (S3)
                                    │
                                    ▼
                              Amazon Athena (5+ views, benchmark)
                                    │
                                    ▼
                             S3 curated/ (KPI aggregates)
                                    │
                                    ▼
                          Amazon QuickSight (4+ visualizations)

Cross-cutting:
  ORCHESTRATION: run_pipeline.sh (bash + AWS CLI)
  SECURITY:      LabRole · Bucket Policy · .gitignore
```

---

## 5. Sensitive Data Handling

The dataset contains GPS coordinates (latitude/longitude) of emergency vehicles and incident locations. These are simulated coordinates in Madrid — not real personal data. No real individuals appear in the dataset. The Supabase `profiles` table (which contains emails) is **excluded from the pipeline** — we only extract `telemetry_readings`, `incidents`, and `anomalies`.
