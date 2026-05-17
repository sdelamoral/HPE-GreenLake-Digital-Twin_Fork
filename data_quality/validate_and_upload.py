
"""
Automated Data Quality Validation with S3 Upload
Runs validation, generates reports, uploads to S3
"""
import subprocess
import sys
import boto3
from pathlib import Path
from datetime import datetime

# Configuration
REPORTS_BUCKET = "emergency-vehicles-reports"
DQ_PREFIX = "data-quality"

def run_validation():
    """Execute validate.py and return report paths"""
    print("=" * 70)
    print("STEP 1: Running Data Quality Validation")
    print("=" * 70)
    
    # Run validate.py
    result = subprocess.run(
        [sys.executable, "data_quality/validate.py"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    # Don't fail on validation issues, only on execution errors
    # A failed check is a valid result, not an error
    if result.stderr and "Traceback" in result.stderr:
        print(result.stderr)
        return None, None
    
    # Find latest JSON report
    log_dir = Path("data_quality/logs")
    json_files = list(log_dir.glob("validation_report_*.json"))
    
    if not json_files:
        print("ERROR: No validation report found")
        return None, None
    
    latest_json = max(json_files, key=lambda p: p.stat().st_mtime)
    return latest_json, None

def generate_html(json_path):
    """Generate HTML report from JSON"""
    print("\n" + "=" * 70)
    print("STEP 2: Generating HTML Report")
    print("=" * 70)
    
    result = subprocess.run(
        [sys.executable, "data_quality/generate_html.py", str(json_path)],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    
    if result.returncode != 0:
        print(result.stderr)
        return None
    
    # Find HTML report (same name as JSON)
    html_path = json_path.with_suffix('.html')
    
    if not html_path.exists():
        print(f"ERROR: HTML report not found: {html_path}")
        return None
    
    return html_path

def upload_to_s3(json_path, html_path):
    """Upload reports to S3"""
    print("\n" + "=" * 70)
    print("STEP 3: Uploading Reports to S3")
    print("=" * 70)
    
    s3 = boto3.client('s3')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create bucket if doesn't exist
    try:
        s3.head_bucket(Bucket=REPORTS_BUCKET)
    except:
        print(f"Creating bucket: {REPORTS_BUCKET}")
        s3.create_bucket(Bucket=REPORTS_BUCKET)
    
    # Upload JSON
    json_key = f"{DQ_PREFIX}/json/validation_report_{timestamp}.json"
    s3.upload_file(
        str(json_path),
        REPORTS_BUCKET,
        json_key,
        ExtraArgs={'ContentType': 'application/json'}
    )
    print(f"✓ Uploaded JSON: s3://{REPORTS_BUCKET}/{json_key}")
    
    # Upload HTML
    html_key = f"{DQ_PREFIX}/html/validation_report_{timestamp}.html"
    s3.upload_file(
        str(html_path),
        REPORTS_BUCKET,
        html_key,
        ExtraArgs={'ContentType': 'text/html'}
    )
    print(f"✓ Uploaded HTML: s3://{REPORTS_BUCKET}/{html_key}")
    
    # Generate public URL for HTML
    html_url = f"https://{REPORTS_BUCKET}.s3.amazonaws.com/{html_key}"
    print(f"\n📊 Report URL: {html_url}")
    
    return json_key, html_key, html_url

def main():
    print("\n" + "=" * 70)
    print("AUTOMATED DATA QUALITY VALIDATION PIPELINE")
    print("=" * 70)
    
    # Step 1: Run validation
    json_path, _ = run_validation()
    if not json_path:
        print("\n✗ Validation failed")
        return False
    
    # Step 2: Generate HTML
    html_path = generate_html(json_path)
    if not html_path:
        print("\n✗ HTML generation failed")
        return False
    
    # Step 3: Upload to S3
    try:
        json_key, html_key, html_url = upload_to_s3(json_path, html_path)
    except Exception as e:
        print(f"\n✗ S3 upload failed: {e}")
        return False
    
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"✓ Validation executed")
    print(f"✓ Reports generated")
    print(f"✓ Reports uploaded to S3")
    print(f"\n📊 View report: {html_url}")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)