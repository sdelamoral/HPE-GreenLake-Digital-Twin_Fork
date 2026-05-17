"""
Generate Sample Data for Emergency Vehicles Digital Twin
Creates realistic CSV files for AWS pipeline testing
"""
import pandas as pd
import uuid
from datetime import datetime, timedelta
import random
import os

print("=" * 60)
print("GENERATING SAMPLE DATA FOR EMERGENCY VEHICLES")
print("=" * 60)

# Create output directory
os.makedirs("sample_data", exist_ok=True)

# ============================================================================
# VEHICLES (18 units)
# ============================================================================
print("\n>>> Generating vehicles...")
vehicles_data = []
vehicle_types = ["police", "ambulance", "fire_truck", "civil_protection"]
makes = ["Ford", "Chevrolet", "Ram", "Mercedes"]
models = ["F-150", "Silverado", "ProMaster", "Sprinter"]

vehicle_ids = []
for i in range(18):
    vid = str(uuid.uuid4())
    vehicle_ids.append(vid)
    
    vehicles_data.append({
        "id": vid,
        "type": vehicle_types[i % len(vehicle_types)],
        "name": f"Unit-{i+1:03d}",
        "plate_number": f"EMG-{i+1:04d}",
        "status": random.choice(["available", "in_service", "en_route", "at_scene"]),
        "year": random.randint(2018, 2024),
        "make": random.choice(makes),
        "model": random.choice(models),
        "current_latitude": 40.4168 + random.uniform(-0.05, 0.05),  # Madrid area
        "current_longitude": -3.7038 + random.uniform(-0.05, 0.05),
        "risk_score": random.randint(0, 100),
        "created_at": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat(),
        "updated_at": datetime.now().isoformat()
    })

vehicles_df = pd.DataFrame(vehicles_data)
vehicles_df.to_csv("sample_data/vehicles.csv", index=False)
print(f"✓ Generated vehicles.csv: {len(vehicles_df):,} rows")

# ============================================================================
# TELEMETRY READINGS (1,800 readings = 100 per vehicle)
# ============================================================================
print("\n>>> Generating telemetry_readings...")
telemetry_data = []
metric_configs = {
    "speed": {"min": 0, "max": 160, "unit": "km/h"},
    "engine_temp": {"min": 70, "max": 120, "unit": "°C"},
    "fuel_level": {"min": 5, "max": 100, "unit": "%"},
    "tire_pressure": {"min": 28, "max": 40, "unit": "PSI"},
    "battery_voltage": {"min": 11.5, "max": 14.8, "unit": "V"},
    "rpm": {"min": 600, "max": 7000, "unit": "RPM"},
    "oil_pressure": {"min": 20, "max": 80, "unit": "PSI"},
    "odometer": {"min": 1000, "max": 150000, "unit": "km"}
}

for vid in vehicle_ids:
    # 100 readings per vehicle
    for j in range(100):
        metric_type = random.choice(list(metric_configs.keys()))
        config = metric_configs[metric_type]
        
        telemetry_data.append({
            "id": str(uuid.uuid4()),
            "vehicle_id": vid,
            "metric_type": metric_type,
            "value": round(random.uniform(config["min"], config["max"]), 2),
            "unit": config["unit"],
            "latitude": 40.4168 + random.uniform(-0.05, 0.05),
            "longitude": -3.7038 + random.uniform(-0.05, 0.05),
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(0, 1440))).isoformat(),
            "created_at": datetime.now().isoformat()
        })

telemetry_df = pd.DataFrame(telemetry_data)
telemetry_df.to_csv("sample_data/telemetry_readings.csv", index=False)
print(f"✓ Generated telemetry_readings.csv: {len(telemetry_df):,} rows")

# ============================================================================
# EVENTS (54 events = 3 per vehicle)
# ============================================================================
print("\n>>> Generating events...")
events_data = []
event_types = ["dispatch", "en_route", "arrived", "completed", "maintenance_alert", "refuel"]

for vid in vehicle_ids:
    # 3 events per vehicle
    for k in range(3):
        events_data.append({
            "id": str(uuid.uuid4()),
            "vehicle_id": vid,
            "event_type": random.choice(event_types),
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 72))).isoformat(),
            "created_at": datetime.now().isoformat()
        })

events_df = pd.DataFrame(events_data)
events_df.to_csv("sample_data/events.csv", index=False)
print(f"✓ Generated events.csv: {len(events_df):,} rows")

# ============================================================================
# ANOMALIES (45 anomalies)
# ============================================================================
print("\n>>> Generating anomalies...")
anomalies_data = []
anomaly_severities = ["info", "warning", "critical"]
anomaly_statuses = ["active", "acknowledged", "resolved"]

for _ in range(45):
    metric_type = random.choice(["engine_temp", "fuel_level", "oil_pressure", "tire_pressure"])
    severity = random.choice(anomaly_severities)
    
    anomalies_data.append({
        "id": str(uuid.uuid4()),
        "vehicle_id": random.choice(vehicle_ids),
        "telemetry_reading_id": str(uuid.uuid4()),
        "anomaly_type": "threshold_breach",
        "metric_type": metric_type,
        "expected_range": '{"min": 0, "max": 100}',
        "actual_value": round(random.uniform(0, 150), 2),
        "severity": severity,
        "status": random.choice(anomaly_statuses),
        "description": f"{metric_type.replace('_', ' ').title()} threshold exceeded",
        "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 168))).isoformat(),
        "resolved_at": (datetime.now() - timedelta(hours=random.randint(0, 24))).isoformat() if random.random() > 0.5 else None,
        "created_at": datetime.now().isoformat()
    })

anomalies_df = pd.DataFrame(anomalies_data)
anomalies_df.to_csv("sample_data/anomalies.csv", index=False)
print(f"✓ Generated anomalies.csv: {len(anomalies_df):,} rows")

# ============================================================================
# INCIDENTS (25 incidents)
# ============================================================================
print("\n>>> Generating incidents...")
incidents_data = []
incident_types = ["fire", "medical", "crime", "accident", "natural_disaster", "road_closure"]
incident_severities = ["info", "warning", "critical"]
incident_statuses = ["reported", "dispatched", "in_progress", "resolved"]

for m in range(25):
    # Assign 1-3 vehicles randomly
    num_vehicles = random.randint(1, 3)
    assigned_vehicles = random.sample(vehicle_ids, num_vehicles)
    
    incidents_data.append({
        "id": str(uuid.uuid4()),
        "title": f"Incident #{m+1:03d}",
        "description": f"Emergency situation requiring immediate response",
        "incident_type": random.choice(incident_types),
        "severity": random.choice(incident_severities),
        "latitude": 40.4168 + random.uniform(-0.08, 0.08),
        "longitude": -3.7038 + random.uniform(-0.08, 0.08),
        "status": random.choice(incident_statuses),
        "assigned_vehicle_ids": str(assigned_vehicles).replace("'", '"'),  # JSON format
        "reported_at": (datetime.now() - timedelta(hours=random.randint(0, 240))).isoformat(),
        "resolved_at": (datetime.now() - timedelta(hours=random.randint(0, 48))).isoformat() if random.random() > 0.6 else None
    })

incidents_df = pd.DataFrame(incidents_data)
incidents_df.to_csv("sample_data/incidents.csv", index=False)
print(f"✓ Generated incidents.csv: {len(incidents_df):,} rows")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 60)
print("GENERATION COMPLETE")
print("=" * 60)
print(f"vehicles:           {len(vehicles_df):>6,} rows")
print(f"telemetry_readings: {len(telemetry_df):>6,} rows")
print(f"events:             {len(events_df):>6,} rows")
print(f"anomalies:          {len(anomalies_df):>6,} rows")
print(f"incidents:          {len(incidents_df):>6,} rows")
print("=" * 60)
print(f"\nTotal: {len(vehicles_df) + len(telemetry_df) + len(events_df) + len(anomalies_df) + len(incidents_df):,} rows")
print("\nFiles saved to: sample_data\\")
print("\nNext steps:")
print("  1. Run: python pipeline\\ingest.py")
print("  2. Run: python pipeline\\transform.py")