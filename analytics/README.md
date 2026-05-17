# Analytics — Role 3

**Role:** Analytics Engineer
**Owner:** [Nombre]

## Responsibilities

- Design and justify partitioning strategy (see `docs/technical_decisions.md` ADR-02)
- Create 5+ Athena views in `analytics/views/`
- Run mandatory benchmark: 3 queries CSV vs Parquet+partition
- Build QuickSight dashboard with 4+ visualizations

## Deliverables (to be added here)

- `views/` — `.sql` files for each Athena view
- `benchmark.md` — Comparison table (time + bytes scanned) with analysis
- `dashboard.pdf` — QuickSight screenshots

## Planned Views

| View | Description |
|------|-------------|
| `v_telemetry_daily_avg` | Daily average per vehicle per metric type |
| `v_anomaly_trend_weekly` | Weekly anomaly count by metric and severity |
| `v_incident_response_time` | Time from reported to resolved per incident type |
| `v_vehicle_risk_summary` | Latest risk score per vehicle with anomaly count |
| `v_incident_hotspots` | Incident counts grouped by geographic zone |

## Benchmark Format

| Query | Format | Time | Bytes scanned |
|-------|--------|------|---------------|
| Q1: total readings/year | CSV | — | — |
| Q1: total readings/year | Parquet+partition | — | — |
| Q2: avg engine_temp by vehicle_type | CSV | — | — |
| Q2: avg engine_temp by vehicle_type | Parquet+partition | — | — |
| Q3: anomaly count by severity/month | CSV | — | — |
| Q3: anomaly count by severity/month | Parquet+partition | — | — |

*(to be filled after running benchmarks in Athena)*
