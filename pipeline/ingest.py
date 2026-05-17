#!/usr/bin/env python3
"""
CSV to S3 Raw Ingestion Pipeline
Uploads CSV datasets to S3 raw bucket with partitioning by date
"""
import boto3
import os
from datetime import datetime
from pathlib import Path

# Configuration
S3_BUCKET = "emergency-vehicles-raw"
S3_PREFIX = "raw/"
LOCAL_CSV_DIR = "./sample_data"

def upload_to_s3(local_path: str, s3_key: str):
    """Upload single CSV file to S3"""
    s3 = boto3.client('s3')
    try:
        s3.upload_file(local_path, S3_BUCKET, s3_key)
        print(f"✓ Uploaded: {local_path} → s3://{S3_BUCKET}/{s3_key}")
    except Exception as e:
        print(f"✗ Failed: {local_path} - {e}")

def ingest_csvs():
    """
    Batch upload all CSV files with date partitioning
    Structure: s3://bucket/raw/table_name/year=YYYY/month=MM/day=DD/file.csv
    """
    date_partition = datetime.now().strftime("year=%Y/month=%m/day=%d")
    
    csv_files = {
        "vehicles": "vehicles.csv",
        "telemetry_readings": "telemetry_readings.csv",
        "events": "events.csv",
        "anomalies": "anomalies.csv",
        "incidents": "incidents.csv"
    }
    
    for table_name, filename in csv_files.items():
        local_file = os.path.join(LOCAL_CSV_DIR, filename)
        
        if not os.path.exists(local_file):
            print(f"⚠ Skipping {filename} - file not found")
            continue
        
        # S3 key with partitioning
        s3_key = f"{S3_PREFIX}{table_name}/{date_partition}/{filename}"
        upload_to_s3(local_file, s3_key)

if __name__ == "__main__":
    print("=== CSV to S3 Ingestion ===")
    ingest_csvs()
    print("\n✓ Ingestion complete")
