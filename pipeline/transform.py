#!/usr/bin/env python3
"""
Transform CSV → Parquet with Schema Alignment
Reads from S3 raw, transforms to Parquet, writes to S3 processed
"""
import boto3
import pandas as pd
import io
from datetime import datetime

# Configuration
RAW_BUCKET = "emergency-vehicles-raw"
PROCESSED_BUCKET = "emergency-vehicles-processed"
RAW_PREFIX = "raw/"
PROCESSED_PREFIX = "processed/"

# Schema definitions aligned to domain model
SCHEMAS = {
    "vehicles": {
        "id": "string",
        "type": "string",
        "name": "string",
        "plate_number": "string",
        "status": "string",
        "year": "int64",
        "make": "string",
        "model": "string",
        "current_latitude": "float64",
        "current_longitude": "float64",
        "risk_score": "int64",
        "created_at": "datetime64[ns]",
        "updated_at": "datetime64[ns]"
    },
    "telemetry_readings": {
        "id": "string",
        "vehicle_id": "string",
        "metric_type": "string",
        "value": "float64",
        "unit": "string",
        "latitude": "float64",
        "longitude": "float64",
        "timestamp": "datetime64[ns]",
        "created_at": "datetime64[ns]"
    },
    "events": {
        "id": "string",
        "vehicle_id": "string",
        "event_type": "string",
        "timestamp": "datetime64[ns]",
        "created_at": "datetime64[ns]"
    },
    "anomalies": {
        "id": "string",
        "vehicle_id": "string",
        "telemetry_reading_id": "string",
        "anomaly_type": "string",
        "metric_type": "string",
        "expected_range": "string",
        "actual_value": "float64",
        "severity": "string",
        "status": "string",
        "description": "string",
        "timestamp": "datetime64[ns]",
        "resolved_at": "datetime64[ns]",
        "created_at": "datetime64[ns]"
    },
    "incidents": {
        "id": "string",
        "title": "string",
        "description": "string",
        "incident_type": "string",
        "severity": "string",
        "latitude": "float64",
        "longitude": "float64",
        "status": "string",
        "assigned_vehicle_ids": "string",
        "reported_at": "datetime64[ns]",
        "resolved_at": "datetime64[ns]"
    }
}

def read_csv_from_s3(bucket: str, key: str) -> pd.DataFrame:
    """Download and parse CSV from S3"""
    s3 = boto3.client('s3')
    obj = s3.get_object(Bucket=bucket, Key=key)
    return pd.read_csv(io.BytesIO(obj['Body'].read()))

def apply_schema(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """Cast DataFrame columns to specified types"""
    for col, dtype in schema.items():
        if col in df.columns:
            if dtype.startswith("datetime"):
                df[col] = pd.to_datetime(df[col], errors='coerce')
            else:
                df[col] = df[col].astype(dtype, errors='ignore')
    return df

def write_parquet_to_s3(df: pd.DataFrame, bucket: str, key: str):
    """Write DataFrame as Parquet to S3"""
    s3 = boto3.client('s3')
    parquet_buffer = io.BytesIO()
    df.to_parquet(parquet_buffer, engine='pyarrow', index=False, compression='snappy')
    parquet_buffer.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=parquet_buffer.getvalue())

def transform_table(table_name: str, date_partition: str):
    """Transform single table from CSV to Parquet"""
    # Input: s3://raw-bucket/raw/table_name/year=YYYY/month=MM/day=DD/*.csv
    raw_key = f"{RAW_PREFIX}{table_name}/{date_partition}/{table_name}.csv"
    
    # Output: s3://processed-bucket/processed/table_name/year=YYYY/month=MM/day=DD/data.parquet
    processed_key = f"{PROCESSED_PREFIX}{table_name}/{date_partition}/data.parquet"
    
    try:
        # Read CSV
        df = read_csv_from_s3(RAW_BUCKET, raw_key)
        print(f"✓ Read {len(df)} rows from {table_name}")
        
        # Apply schema
        df = apply_schema(df, SCHEMAS[table_name])
        print(f"✓ Applied schema to {table_name}")
        
        # Write Parquet
        write_parquet_to_s3(df, PROCESSED_BUCKET, processed_key)
        print(f"✓ Wrote Parquet: s3://{PROCESSED_BUCKET}/{processed_key}")
        
    except Exception as e:
        print(f"✗ Failed to transform {table_name}: {e}")

def transform_all():
    """Transform all tables for current date partition"""
    date_partition = datetime.now().strftime("year=%Y/month=%m/day=%d")
    
    tables = ["vehicles", "telemetry_readings", "events", "anomalies", "incidents"]
    
    for table in tables:
        print(f"\n--- Transforming {table} ---")
        transform_table(table, date_partition)

if __name__ == "__main__":
    print("=== CSV → Parquet Transformation ===")
    transform_all()
    print("\n✓ Transformation complete")
