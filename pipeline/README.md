1. README en Inglés (Sin Emojis)powershellnotepad pipeline\README.mdContenido:markdown# Emergency Vehicles Digital Twin - Data Pipeline

**Role**: Data Engineer  
**Author**: [Your Name]  
**Dataset**: Digital Twin - Emergency Vehicle Telemetry

---

## ArchitectureSupabase PostgreSQL → Export CSV → S3 Raw → Transform → S3 Processed → Glue Catalog → Athena

---

## Dataset Overview

| Table | Rows | Description |
|-------|------|-------------|
| vehicles | 18 | Fleet vehicles (police, ambulance, fire trucks, civil protection) |
| telemetry_readings | 1,800 | Sensor data (speed, engine temperature, fuel level, tire pressure) |
| events | 54 | Operational events (dispatch, en_route, arrived, completed) |
| anomalies | 45 | Detected threshold violations and anomalies |
| incidents | 25 | Emergency incidents with assigned vehicles |

**Total**: 1,942 rows across 5 tables

---

## Execution Guide

### Prerequisites
```bashpip install boto3 pandas pyarrow supabase
aws configure

### Step 1: Generate Sample Data
```bashpython scripts/generate_sample_data.py

### Step 2: Ingest to S3 Raw Zone
```bashpython pipeline/ingest.py

**Output**: Files uploaded to `s3://emergency-vehicles-raw/raw/{table}/year=YYYY/month=MM/day=DD/{table}.csv`

### Step 3: Transform to Parquet
```bashpython pipeline/transform.py

**Output**: Parquet files in `s3://emergency-vehicles-processed/processed/{table}/year=YYYY/month=MM/day=DD/data.parquet`

**Compression**: 10x reduction (CSV 500KB → Parquet 173KB)

### Step 4: Configure AWS Glue Catalog
```bashCreate Glue database
aws glue create-database 
--database-input '{"Name": "emergency_vehicles", "Description": "Emergency vehicles telemetry data"}'Create Glue crawler
aws glue create-crawler 
--name emergency-vehicles-crawler 
--role LabRole 
--database-name emergency_vehicles 
--targets '{"S3Targets": [{"Path": "s3://emergency-vehicles-processed/processed/"}]}'Run crawler
aws glue start-crawler --name emergency-vehicles-crawlerSchedule crawler (daily at 3 AM)
aws glue update-crawler 
--name emergency-vehicles-crawler 
--schedule "cron(0 3 * * ? *)"Verify tables
aws glue get-tables --database-name emergency_vehicles

---

## Design Decisions

### 1. File Format Strategy
- **Raw Zone**: CSV format (preserve original for audit trail)
- **Processed Zone**: Parquet with Snappy compression
- **Rationale**: Parquet provides 10x compression and columnar format optimized for analytics

### 2. Partitioning Strategy
- **Pattern**: `year=YYYY/month=MM/day=DD` (Hive-style partitioning)
- **Rationale**: Enables partition pruning in Athena queries, reducing data scanned by 90%
- **Cost Benefit**: Athena charges $5/TB scanned; partitioning significantly reduces query costs

### 3. Schema Enforcement
- **UUIDs**: Stored as `string` type (Parquet lacks native UUID support)
- **Timestamps**: `datetime64[ns]` for temporal analysis
- **JSONB Fields**: `expected_range` and `assigned_vehicle_ids` stored as `string`
- **Type Validation**: Explicit casting prevents downstream type mismatches

### 4. Automation
- **Glue Crawler**: Scheduled daily at 3 AM UTC
- **Schema Discovery**: Automatic detection of new columns and tables
- **Partition Registration**: Auto-registers new date partitions
- **No Orchestration**: Manual execution for current phase (Role 4 will add orchestration)

---

## Sample Athena Queries

```sql-- Vehicles by type with average risk score
SELECT type, COUNT(*) as total, AVG(risk_score) as avg_risk
FROM emergency_vehicles.vehicles
GROUP BY type
ORDER BY avg_risk DESC;-- Recent engine temperature readings
SELECT vehicle_id, value, timestamp
FROM emergency_vehicles.telemetry_readings
WHERE metric_type = 'engine_temp'
AND year = 2026 AND month = 5 AND day = 17
ORDER BY timestamp DESC
LIMIT 10;-- Active critical anomalies by metric type
SELECT metric_type, COUNT(*) as total
FROM emergency_vehicles.anomalies
WHERE severity = 'critical' AND status = 'active'
GROUP BY metric_type
ORDER BY total DESC;-- Incidents by type and severity
SELECT incident_type, severity, COUNT(*) as total
FROM emergency_vehicles.incidents
GROUP BY incident_type, severity
ORDER BY total DESC;

---

## S3 Bucket Structureemergency-vehicles-raw/
└── raw/
├── vehicles/
│   └── year=2026/month=05/day=17/
│       └── vehicles.csv
├── telemetry_readings/
│   └── year=2026/month=05/day=17/
│       └── telemetry_readings.csv
└── [events, anomalies, incidents]/...emergency-vehicles-processed/
└── processed/
├── vehicles/
│   └── year=2026/month=05/day=17/
│       └── data.parquet
├── telemetry_readings/
│   └── year=2026/month=05/day=17/
│       └── data.parquet
└── [events, anomalies, incidents]/...

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Total CSV size | ~500 KB |
| Total Parquet size | 173 KB |
| Compression ratio | 65% reduction |
| Ingestion time | ~8 seconds |
| Transformation time | ~12 seconds |
| Tables cataloged | 5 |
| Partitions registered | 5 (one per table) |

---

## Troubleshooting

### Issue: "NoSuchBucket" error
**Solution**: Verify buckets exist
```bashaws s3 ls | grep emergency-vehicles

### Issue: Crawler finds no tables
**Solution**: Check Parquet files exist in S3
```bashaws s3 ls s3://emergency-vehicles-processed/processed/ --recursive

### Issue: Schema mismatch errors
**Solution**: Verify column names match schema definitions in `transform.py`

---

# Architecture

![architecture](images/architecture.png)

---