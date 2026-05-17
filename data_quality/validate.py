"""
Data Quality Validation for Emergency Vehicles Digital Twin
Implements 9 validation rules with detailed reporting
"""
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
import boto3
import io

# ============================================================================
# CONFIGURATION
# ============================================================================

DATA_DIR = Path("sample_data")
REPORT_DIR = Path("data_quality/logs")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

CONSTRAINTS = {
    # Categorical values (from Digital Twin doc page 28-29)
    "vehicle_types": ["police", "ambulance", "fire_truck", "civil_protection", "hybrid"],
    "vehicle_status": ["available", "in_service", "en_route", "at_scene", "maintenance", "offline"],
    "event_types": ["dispatch", "en_route", "arrived", "completed", "maintenance_alert", "refuel", "equipment_check"],
    "severity_levels": ["info", "warning", "critical"],
    "metric_types": ["speed", "engine_temp", "fuel_level", "tire_pressure", "battery_voltage", "rpm", "oil_pressure", "odometer"],
    "incident_types": ["fire", "medical", "crime", "accident", "natural_disaster", "road_closure"],
    "anomaly_status": ["active", "acknowledged", "resolved"],
    
    # Telemetry ranges (from Digital Twin doc page 17)
    "telemetry_ranges": {
        "speed": {"min": 0, "max": 160, "unit": "km/h"},
        "engine_temp": {"min": 70, "max": 120, "unit": "°C"},
        "fuel_level": {"min": 5, "max": 100, "unit": "%"},
        "tire_pressure": {"min": 28, "max": 40, "unit": "PSI"},
        "battery_voltage": {"min": 11.5, "max": 14.8, "unit": "V"},
        "rpm": {"min": 600, "max": 7000, "unit": "RPM"},
        "oil_pressure": {"min": 20, "max": 80, "unit": "PSI"},
        "odometer": {"min": 0, "max": 999999, "unit": "km"}
    },
    
    # Temporal bounds
    "system_start_date": "2020-01-01",
    "future_tolerance_hours": 1,
    
    # Geographic bounds (Madrid area)
    "geo_bounds": {
        "lat_min": 40.3,
        "lat_max": 40.6,
        "lon_min": -3.9,
        "lon_max": -3.5
    },
    
    # Business rules
    "risk_score_range": {"min": 0, "max": 100}
}

# ============================================================================
# VALIDATION RULES
# ============================================================================

def rule_dq01_primary_key_uniqueness(data_dict):
    """
    DQ-01: Primary Key Uniqueness
    Every table must have unique IDs with no duplicates
    """
    results = {}
    for table_name, df in data_dict.items():
        if 'id' in df.columns:
            total = len(df)
            unique = df['id'].nunique()
            duplicates = total - unique
            
            results[table_name] = {
                "rule_id": "DQ-01",
                "passed": duplicates == 0,
                "total_rows": total,
                "unique_ids": unique,
                "duplicates": duplicates,
                "message": f"Found {duplicates} duplicate IDs" if duplicates > 0 else "All IDs unique"
            }
    return results

def rule_dq02_foreign_key_integrity(data_dict):
    """
    DQ-02: Foreign Key Integrity
    All foreign keys must reference existing primary keys
    """
    results = {}
    
    # Define FK relationships
    fk_checks = [
        ("telemetry_readings", "vehicle_id", "vehicles", "id"),
        ("events", "vehicle_id", "vehicles", "id"),
        ("anomalies", "vehicle_id", "vehicles", "id"),
        ("anomalies", "telemetry_reading_id", "telemetry_readings", "id")
    ]
    
    for child_table, fk_col, parent_table, pk_col in fk_checks:
        if child_table in data_dict and parent_table in data_dict:
            child_df = data_dict[child_table]
            parent_df = data_dict[parent_table]
            
            # Check non-null FKs exist in parent
            child_fks = child_df[fk_col].dropna()
            parent_pks = set(parent_df[pk_col])
            
            orphans = child_fks[~child_fks.isin(parent_pks)]
            
            results[f"{child_table}.{fk_col}"] = {
                "rule_id": "DQ-02",
                "passed": len(orphans) == 0,
                "total_references": len(child_fks),
                "orphaned_records": len(orphans),
                "message": f"Found {len(orphans)} orphaned references" if len(orphans) > 0 else "All FKs valid"
            }
    
    return results

def rule_dq03_enum_validity(data_dict):
    """
    DQ-03: Enum Value Validity
    Categorical columns must only contain allowed values
    """
    results = {}
    
    enum_checks = [
        ("vehicles", "type", CONSTRAINTS["vehicle_types"]),
        ("vehicles", "status", CONSTRAINTS["vehicle_status"]),
        ("events", "event_type", CONSTRAINTS["event_types"]),
        ("anomalies", "severity", CONSTRAINTS["severity_levels"]),
        ("anomalies", "status", CONSTRAINTS["anomaly_status"]),
        ("incidents", "incident_type", CONSTRAINTS["incident_types"]),
        ("incidents", "severity", CONSTRAINTS["severity_levels"]),
        ("telemetry_readings", "metric_type", CONSTRAINTS["metric_types"])
    ]
    
    for table_name, column, allowed_values in enum_checks:
        if table_name in data_dict and column in data_dict[table_name].columns:
            df = data_dict[table_name]
            values = df[column].dropna()
            invalid = values[~values.isin(allowed_values)]
            
            results[f"{table_name}.{column}"] = {
                "rule_id": "DQ-03",
                "passed": len(invalid) == 0,
                "total_values": len(values),
                "invalid_count": len(invalid),
                "invalid_values": invalid.unique().tolist() if len(invalid) > 0 else [],
                "message": f"Found {len(invalid)} invalid values" if len(invalid) > 0 else "All values valid"
            }
    
    return results

def rule_dq04_telemetry_ranges(data_dict):
    """
    DQ-04: Telemetry Value Ranges
    Sensor readings must fall within physically possible ranges
    """
    results = {}
    
    if "telemetry_readings" in data_dict:
        df = data_dict["telemetry_readings"]
        
        for metric_type, bounds in CONSTRAINTS["telemetry_ranges"].items():
            metric_data = df[df["metric_type"] == metric_type]
            
            if len(metric_data) > 0:
                out_of_range = metric_data[
                    (metric_data["value"] < bounds["min"]) | 
                    (metric_data["value"] > bounds["max"])
                ]
                
                results[f"telemetry.{metric_type}"] = {
                    "rule_id": "DQ-04",
                    "passed": len(out_of_range) == 0,
                    "total_readings": len(metric_data),
                    "out_of_range": len(out_of_range),
                    "min_allowed": bounds["min"],
                    "max_allowed": bounds["max"],
                    "unit": bounds["unit"],
                    "message": f"Found {len(out_of_range)} readings outside range [{bounds['min']}, {bounds['max']}] {bounds['unit']}"
                               if len(out_of_range) > 0 else f"All readings within [{bounds['min']}, {bounds['max']}] {bounds['unit']}"
                }
    
    return results

def rule_dq05_timestamp_validity(data_dict):
    """
    DQ-05: Timestamp Validity
    Timestamps must be >= system start date and not too far in the future
    """
    results = {}
    
    start_date = pd.to_datetime(CONSTRAINTS["system_start_date"])
    future_limit = pd.Timestamp.now() + timedelta(hours=CONSTRAINTS["future_tolerance_hours"])
    
    timestamp_cols = [
        ("vehicles", "created_at"),
        ("vehicles", "updated_at"),
        ("telemetry_readings", "timestamp"),
        ("telemetry_readings", "created_at"),
        ("events", "timestamp"),
        ("anomalies", "timestamp"),
        ("incidents", "reported_at")
    ]
    
    for table_name, col in timestamp_cols:
        if table_name in data_dict and col in data_dict[table_name].columns:
            df = data_dict[table_name]
            timestamps = pd.to_datetime(df[col], errors='coerce').dropna()
            
            too_old = timestamps[timestamps < start_date]
            too_new = timestamps[timestamps > future_limit]
            
            results[f"{table_name}.{col}"] = {
                "rule_id": "DQ-05",
                "passed": len(too_old) == 0 and len(too_new) == 0,
                "total_timestamps": len(timestamps),
                "too_old": len(too_old),
                "too_new": len(too_new),
                "message": f"Found {len(too_old)} too old, {len(too_new)} too new" 
                           if (len(too_old) > 0 or len(too_new) > 0) 
                           else "All timestamps valid"
            }
    
    return results

def rule_dq06_required_fields(data_dict):
    """
    DQ-06: Required Field Completeness
    Critical fields must not have NULL values
    """
    results = {}
    
    required_fields = [
        ("vehicles", ["id", "type", "name", "plate_number", "status"]),
        ("telemetry_readings", ["id", "vehicle_id", "metric_type", "value", "timestamp"]),
        ("events", ["id", "vehicle_id", "event_type", "timestamp"]),
        ("anomalies", ["id", "vehicle_id", "severity", "status", "timestamp"]),
        ("incidents", ["id", "incident_type", "severity", "latitude", "longitude"])
    ]
    
    for table_name, fields in required_fields:
        if table_name in data_dict:
            df = data_dict[table_name]
            
            for field in fields:
                if field in df.columns:
                    null_count = df[field].isna().sum()
                    
                    results[f"{table_name}.{field}"] = {
                        "rule_id": "DQ-06",
                        "passed": null_count == 0,
                        "total_rows": len(df),
                        "null_count": null_count,
                        "message": f"Found {null_count} NULL values" if null_count > 0 else "No NULLs"
                    }
    
    return results

def rule_dq07_risk_score_range(data_dict):
    """
    DQ-07: Risk Score Range
    Vehicle risk scores must be between 0 and 100
    """
    results = {}
    
    if "vehicles" in data_dict and "risk_score" in data_dict["vehicles"].columns:
        df = data_dict["vehicles"]
        scores = df["risk_score"].dropna()
        
        min_score = CONSTRAINTS["risk_score_range"]["min"]
        max_score = CONSTRAINTS["risk_score_range"]["max"]
        
        out_of_range = scores[(scores < min_score) | (scores > max_score)]
        
        results["vehicles.risk_score"] = {
            "rule_id": "DQ-07",
            "passed": len(out_of_range) == 0,
            "total_scores": len(scores),
            "out_of_range": len(out_of_range),
            "min_allowed": min_score,
            "max_allowed": max_score,
            "message": f"Found {len(out_of_range)} scores outside [0, 100]" 
                       if len(out_of_range) > 0 
                       else "All risk scores within [0, 100]"
        }
    
    return results

def rule_dq08_event_sequence(data_dict):
    """
    DQ-08: Event Sequence Logic
    Events for same vehicle should follow logical temporal order
    """
    results = {}
    
    if "events" in data_dict:
        df = data_dict["events"].copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # Check for time-travel (events out of chronological order per vehicle)
        df_sorted = df.sort_values(["vehicle_id", "timestamp"])
        
        violations = 0
        for vehicle_id in df["vehicle_id"].unique():
            vehicle_events = df_sorted[df_sorted["vehicle_id"] == vehicle_id]
            
            # Check if timestamps are monotonically increasing
            if not vehicle_events["timestamp"].is_monotonic_increasing:
                violations += 1
        
        results["events.sequence"] = {
            "rule_id": "DQ-08",
            "passed": violations == 0,
            "total_vehicles_with_events": df["vehicle_id"].nunique(),
            "vehicles_with_violations": violations,
            "message": f"Found {violations} vehicles with out-of-order events" 
                       if violations > 0 
                       else "All event sequences valid"
        }
    
    return results

def rule_dq09_geospatial_validity(data_dict):
    """
    DQ-09: Geospatial Validity
    Coordinates must be within Madrid operational area
    """
    results = {}
    
    geo_cols = [
        ("vehicles", "current_latitude", "current_longitude"),
        ("telemetry_readings", "latitude", "longitude"),
        ("incidents", "latitude", "longitude")
    ]
    
    bounds = CONSTRAINTS["geo_bounds"]
    
    for table_name, lat_col, lon_col in geo_cols:
        if table_name in data_dict and lat_col in data_dict[table_name].columns:
            df = data_dict[table_name]
            
            # Drop NULLs for optional coordinates
            coords = df[[lat_col, lon_col]].dropna()
            
            out_of_bounds = coords[
                (coords[lat_col] < bounds["lat_min"]) |
                (coords[lat_col] > bounds["lat_max"]) |
                (coords[lon_col] < bounds["lon_min"]) |
                (coords[lon_col] > bounds["lon_max"])
            ]
            
            results[f"{table_name}.coordinates"] = {
                "rule_id": "DQ-09",
                "passed": len(out_of_bounds) == 0,
                "total_coordinates": len(coords),
                "out_of_bounds": len(out_of_bounds),
                "bounds": bounds,
                "message": f"Found {len(out_of_bounds)} coordinates outside Madrid area" 
                           if len(out_of_bounds) > 0 
                           else "All coordinates within Madrid bounds"
            }
    
    return results

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def load_data():
    """Load all Parquet files from S3 processed zone"""
    import boto3
    import io
    from datetime import datetime
    
    s3 = boto3.client('s3')
    data = {}
    
    # Configuration
    BUCKET = "emergency-vehicles-processed"
    PREFIX = "processed/"
    
    # Get current date partition
    today = datetime.now()
    partition = f"year={today.year}/month={today.month:02d}/day={today.day:02d}"
    
    tables = ["vehicles", "telemetry_readings", "events", "anomalies", "incidents"]
    
    print(f"Reading from S3: s3://{BUCKET}/{PREFIX}")
    print(f"Date partition: {partition}\n")
    
    for table in tables:
        s3_key = f"{PREFIX}{table}/{partition}/data.parquet"
        
        try:
            # Download Parquet from S3
            obj = s3.get_object(Bucket=BUCKET, Key=s3_key)
            parquet_data = io.BytesIO(obj['Body'].read())
            
            # Read Parquet
            data[table] = pd.read_parquet(parquet_data, engine='pyarrow')
            print(f"[OK] Loaded {table}: {len(data[table]):,} rows from S3")
            
        except s3.exceptions.NoSuchKey:
            print(f"[ERROR] Not found: s3://{BUCKET}/{s3_key}")
        except Exception as e:
            print(f"[ERROR] Error loading {table}: {e}")
    
    return data

def run_all_validations(data):
    """Execute all validation rules"""
    all_results = {}
    
    rules = [
        ("DQ-01: Primary Key Uniqueness", rule_dq01_primary_key_uniqueness),
        ("DQ-02: Foreign Key Integrity", rule_dq02_foreign_key_integrity),
        ("DQ-03: Enum Value Validity", rule_dq03_enum_validity),
        ("DQ-04: Telemetry Value Ranges", rule_dq04_telemetry_ranges),
        ("DQ-05: Timestamp Validity", rule_dq05_timestamp_validity),
        ("DQ-06: Required Field Completeness", rule_dq06_required_fields),
        ("DQ-07: Risk Score Range", rule_dq07_risk_score_range),
        ("DQ-08: Event Sequence Logic", rule_dq08_event_sequence),
        ("DQ-09: Geospatial Validity", rule_dq09_geospatial_validity)
    ]
    
    for rule_name, rule_func in rules:
        print(f"\nRunning {rule_name}...")
        results = rule_func(data)
        all_results[rule_name] = results
    
    return all_results

def convert_to_json_serializable(obj):
    """Convert numpy types to native Python types for JSON serialization"""
    import numpy as np
    
    if isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

def generate_summary(all_results):
    """Generate summary statistics"""
    total_checks = 0
    passed_checks = 0
    
    for rule_name, rule_results in all_results.items():
        for check_name, check_result in rule_results.items():
            total_checks += 1
            if check_result["passed"]:
                passed_checks += 1
    
    return {
        "total_checks": int(total_checks),
        "passed": int(passed_checks),
        "failed": int(total_checks - passed_checks),
        "pass_rate": round((passed_checks / total_checks * 100), 2) if total_checks > 0 else 0
    }

def main():
    print("=" * 70)
    print("DATA QUALITY VALIDATION - EMERGENCY VEHICLES DIGITAL TWIN")
    print("=" * 70)
    
    # Load data
    print("\nLoading datasets...")
    data = load_data()
    
    # Run validations
    print("\n" + "=" * 70)
    print("EXECUTING VALIDATION RULES")
    print("=" * 70)
    results = run_all_validations(data)
    
    # Generate summary
    summary = generate_summary(results)
    
    # Save report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORT_DIR / f"validation_report_{timestamp}.json"
    
    report = {
        "execution_timestamp": datetime.now().isoformat(),
        "summary": summary,
        "results": convert_to_json_serializable(results)  # ← Convertir aquí
    }
    
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Total Checks:  {summary['total_checks']}")
    print(f"Passed:        {summary['passed']}")
    print(f"Failed:        {summary['failed']}")
    print(f"Pass Rate:     {summary['pass_rate']}%")
    print(f"\nReport saved: {report_path}")
    
    return summary['failed'] == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)