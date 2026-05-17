#!/usr/bin/env python3
"""
Export Emergency Vehicles Digital Twin Data from Supabase to CSV
Purpose: Generate CSV files for AWS Data Engineering pipeline
"""
import os
import sys
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta

# Supabase credentials from your project
SUPABASE_URL = 'https://wogeqzszceqjksiolbpj.supabase.co'  # From your emergency-vehicles.xyz
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")  # Set this as env var (use role key for full access if needed)

OUTPUT_DIR = "./sample_data"

def export_table(supabase, table_name, days_back=30):
    """Export table to CSV with optional time filter for time-series data"""
    
    print(f"\n>>> Exporting {table_name}...")
    
    try:
        # For time-series tables, filter by recent data only
        if table_name in ["telemetry_readings", "events"]:
            cutoff = datetime.now() - timedelta(days=days_back)
            response = supabase.table(table_name)\
                .select("*")\
                .gte("timestamp", cutoff.isoformat())\
                .execute()
        else:
            response = supabase.table(table_name).select("*").execute()
        
        # Convert to DataFrame
        df = pd.DataFrame(response.data)
        
        if len(df) == 0:
            print(f"⚠ {table_name} is empty, skipping")
            return False
        
        # Export to CSV
        output_path = f"{OUTPUT_DIR}/{table_name}.csv"
        df.to_csv(output_path, index=False)
        
        print(f"✓ Exported {len(df):,} rows × {len(df.columns)} columns")
        print(f"  File: {output_path} ({os.path.getsize(output_path):,} bytes)")
        
        return True
        
    except Exception as e:
        print(f"✗ Failed to export {table_name}: {e}")
        return False

def main():
    # Check for API key
    if not SUPABASE_KEY:
        print("✗ Error: SUPABASE_ANON_KEY environment variable not set")
        print("\nSet it with:")
        print("  export SUPABASE_ANON_KEY='your-key-here'")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Initialize Supabase client
    print("Connecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✓ Connected")
    
    # Tables to export (in dependency order)
    tables = [
        "vehicles",           # Master data (no FKs)
        "telemetry_readings", # FK to vehicles
        "events",            # FK to vehicles
        "anomalies",         # FK to vehicles, telemetry_readings
        "incidents"          # FK to vehicles (array)
    ]
    
    print("\n" + "=" * 60)
    print("EXPORTING DATA FROM SUPABASE TO CSV")
    print("=" * 60)
    
    success_count = 0
    for table in tables:
        if export_table(supabase, table):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"EXPORT COMPLETE: {success_count}/{len(tables)} tables")
    print("=" * 60)
    print(f"\nCSV files saved to: {OUTPUT_DIR}/")
    print("\nNext steps:")
    print("  1. Review the CSV files")
    print("  2. Run: python pipeline/ingest.py")
    print("  3. Run: python pipeline/transform.py")

if __name__ == "__main__":
    main()