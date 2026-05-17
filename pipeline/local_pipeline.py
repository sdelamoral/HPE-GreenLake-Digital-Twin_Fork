"""
local_pipeline.py — Plan B backup demo (no AWS required)

Runs the full pipeline locally using pandas + pyarrow + DuckDB:
  1. Read CSV samples from --input folder
  2. Validate schemas (basic DQ checks)
  3. Align schemas (CSV → Parquet, same logic as Glue ETL job)
  4. Write Parquet to --output folder with partition structure
  5. Run 3 benchmark queries with DuckDB (Athena equivalent)

Usage:
  python3 pipeline/local_pipeline.py --input data_samples/ --output /tmp/output/
"""

import argparse
import os
import sys
import time
from pathlib import Path

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    import duckdb
except ImportError:
    print("Missing dependencies. Install: pip install pandas pyarrow duckdb")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Schema alignment (mirrors the Glue ETL job logic)
# ---------------------------------------------------------------------------
METRIC_TYPES = {
    "engine_temp", "fuel_level", "speed", "rpm",
    "battery_voltage", "oil_pressure", "tire_pressure", "mileage", "coolant_temp",
}
SEVERITIES = {"info", "warning", "critical"}
INCIDENT_TYPES = {"fire", "medical", "crime", "accident", "natural_disaster"}


def align_telemetry(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={"timestamp": "event_timestamp"})
    df["source"] = "telemetry_readings"
    df["year"] = pd.to_datetime(df["event_timestamp"]).dt.year
    return df[[
        "id", "vehicle_id", "metric_type", "value", "unit",
        "latitude", "longitude", "event_timestamp", "source", "year",
    ]]


def align_incidents(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={"reported_at": "event_timestamp"})
    df["source"] = "incidents"
    df["year"] = pd.to_datetime(df["event_timestamp"]).dt.year
    # Serialize UUID[] array to string
    if "assigned_vehicle_ids" in df.columns:
        df["assigned_vehicle_ids"] = df["assigned_vehicle_ids"].astype(str)
    return df[[
        "id", "title", "incident_type", "severity",
        "latitude", "longitude", "status", "event_timestamp",
        "assigned_vehicle_ids", "resolved_at", "source", "year",
    ]]


def align_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.rename(columns={"timestamp": "event_timestamp"})
    df["source"] = "anomalies"
    df["year"] = pd.to_datetime(df["event_timestamp"]).dt.year
    return df[[
        "id", "vehicle_id", "metric_type", "actual_value",
        "severity", "status", "description", "event_timestamp",
        "resolved_at", "source", "year",
    ]]


# ---------------------------------------------------------------------------
# Basic DQ validation (mirrors data_quality/validate.py)
# ---------------------------------------------------------------------------
def validate(name: str, df: pd.DataFrame) -> bool:
    errors = []
    if name == "telemetry_readings":
        if df["vehicle_id"].isna().any():
            errors.append("DQ-01 FAIL: vehicle_id has nulls")
        invalid_metrics = ~df["metric_type"].isin(METRIC_TYPES)
        if invalid_metrics.any():
            errors.append(f"DQ-02 FAIL: invalid metric_type values: {df[invalid_metrics]['metric_type'].unique()}")
        if df["event_timestamp"].isna().any():
            errors.append("DQ-04 FAIL: event_timestamp has nulls")
    elif name == "incidents":
        invalid_types = ~df["incident_type"].isin(INCIDENT_TYPES)
        if invalid_types.any():
            errors.append(f"DQ-05 FAIL: invalid incident_type: {df[invalid_types]['incident_type'].unique()}")
        invalid_sev = ~df["severity"].isin(SEVERITIES)
        if invalid_sev.any():
            errors.append(f"DQ-08 FAIL: invalid severity: {df[invalid_sev]['severity'].unique()}")
    elif name == "anomalies":
        if df["vehicle_id"].isna().any():
            errors.append("DQ-01 FAIL: vehicle_id has nulls")
        invalid_sev = ~df["severity"].isin(SEVERITIES)
        if invalid_sev.any():
            errors.append(f"DQ-08 FAIL: invalid severity")

    if errors:
        for e in errors:
            print(f"  ✗ {e}")
        return False
    print(f"  ✓ All DQ checks passed for {name}")
    return True


# ---------------------------------------------------------------------------
# Benchmark queries (DuckDB as local Athena equivalent)
# ---------------------------------------------------------------------------
def run_benchmark(output_dir: Path) -> None:
    print("\n=== BENCHMARK: CSV vs Parquet ===")
    con = duckdb.connect()

    telemetry_csv = str(output_dir.parent.parent / "data_samples" / "telemetry_sample.csv")
    telemetry_parquet = str(output_dir / "telemetry" / "**" / "*.parquet")

    queries = [
        ("Q1: total readings per year",
         f"SELECT year(event_timestamp) as yr, count(*) as n FROM read_csv_auto('{telemetry_csv}') GROUP BY yr",
         f"SELECT year, count(*) as n FROM read_parquet('{telemetry_parquet}', hive_partitioning=true) GROUP BY year"),
        ("Q2: avg engine_temp by vehicle_id",
         f"SELECT vehicle_id, avg(value) FROM read_csv_auto('{telemetry_csv}') WHERE metric_type='engine_temp' GROUP BY vehicle_id",
         f"SELECT vehicle_id, avg(value) FROM read_parquet('{telemetry_parquet}', hive_partitioning=true) WHERE metric_type='engine_temp' GROUP BY vehicle_id"),
    ]

    print(f"{'Query':<40} {'Format':<12} {'Time (s)':>10}")
    print("-" * 65)
    for label, csv_q, parquet_q in queries:
        for fmt, query in [("CSV", csv_q), ("Parquet+part", parquet_q)]:
            try:
                t0 = time.time()
                con.execute(query).fetchall()
                elapsed = time.time() - t0
                print(f"{label:<40} {fmt:<12} {elapsed:>10.3f}")
            except Exception as e:
                print(f"{label:<40} {fmt:<12} {'ERROR':>10}  ({e})")
    con.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Local backup pipeline demo")
    parser.add_argument("--input", required=True, help="Folder with CSV sample files")
    parser.add_argument("--output", required=True, help="Output folder for Parquet files")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = {
        "telemetry_readings": (input_dir / "telemetry_sample.csv", align_telemetry),
        "incidents":          (input_dir / "incidents_sample.csv",  align_incidents),
        "anomalies":          (input_dir / "anomalies_sample.csv",  align_anomalies),
    }

    all_ok = True
    for name, (csv_path, align_fn) in tables.items():
        print(f"\n--- {name} ---")
        if not csv_path.exists():
            print(f"  ⚠ Sample not found: {csv_path}. Skipping.")
            continue

        df = pd.read_csv(csv_path)
        print(f"  Loaded {len(df)} rows, {len(df.columns)} columns")

        df = align_fn(df)
        ok = validate(name, df)
        all_ok = all_ok and ok

        # Write Parquet with Hive partitioning
        table = pa.Table.from_pandas(df)
        part_cols = ["year", "vehicle_type"] if "vehicle_type" in df.columns else ["year"]
        part_cols = [c for c in part_cols if c in df.columns]
        out_path = output_dir / name.replace("_readings", "").replace("_", "/")
        pq.write_to_dataset(table, root_path=str(out_path), partition_cols=part_cols)
        print(f"  Written to {out_path}/")

    print(f"\nDQ overall: {'✅ PASSED' if all_ok else '❌ SOME RULES FAILED'}")

    run_benchmark(output_dir)

    print("\n✅ Local pipeline complete.")
    print(f"   Parquet output: {output_dir}")
    print("   Inspect with:  python3 -c \"import pandas as pd; print(pd.read_parquet('{}'))\"".format(output_dir))


if __name__ == "__main__":
    main()
