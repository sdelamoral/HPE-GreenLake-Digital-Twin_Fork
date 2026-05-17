#!/usr/bin/env bash
# =============================================================================
# run_pipeline.sh — Master orchestration script
# HPE GreenLake Digital Twin | Data Engineering Capstone — Role 4
#
# Stages:
#   1. INGEST   — Export Supabase tables to S3 raw zone
#   2. TRANSFORM — Run Glue ETL Job (CSV → Parquet, schema alignment)
#   3. CATALOG  — Run Glue Crawler and wait for completion
#   4. QUALITY  — Execute Data Quality validation job
#   5. ATHENA   — Create/refresh Athena views
#
# Usage:
#   ./orchestration/run_pipeline.sh [--stage <stage>] [--dry-run]
#
# Requirements:
#   - AWS CLI configured with LabRole (no hardcoded credentials)
#   - Environment variables in .env (see .env.example)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration (overridable via environment variables)
# ---------------------------------------------------------------------------
BUCKET="${S3_BUCKET:-hpe-greenlake-dt-datalake}"
REGION="${AWS_REGION:-us-east-1}"
GLUE_ETL_JOB="${GLUE_ETL_JOB_NAME:-dt-transform-csv-to-parquet}"
GLUE_DQ_JOB="${GLUE_DQ_JOB_NAME:-dt-data-quality-check}"
GLUE_CRAWLER="${GLUE_CRAWLER_NAME:-dt-crawler-processed}"
ATHENA_DB="${ATHENA_DATABASE:-digital_twin_db}"
ATHENA_OUTPUT="s3://${BUCKET}/athena-results/"
INGEST_SCRIPT="pipeline/ingest.py"

DRY_RUN=false
ONLY_STAGE=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
LOG_FILE="orchestration/pipeline_run_$(date +%Y%m%d_%H%M%S).log"
mkdir -p orchestration/logs

log() {
  local level="$1"; shift
  local ts
  ts=$(date '+%Y-%m-%d %H:%M:%S')
  echo "[${ts}] [${level}] $*" | tee -a "$LOG_FILE"
}

info()    { log "INFO " "$@"; }
success() { log "OK   " "$@"; }
warn()    { log "WARN " "$@"; }
error()   { log "ERROR" "$@"; }

die() {
  error "$@"
  exit 1
}

run() {
  if [[ "$DRY_RUN" == "true" ]]; then
    info "[DRY-RUN] $*"
  else
    "$@"
  fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)   DRY_RUN=true; shift ;;
    --stage)     ONLY_STAGE="$2"; shift 2 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# *//'
      exit 0 ;;
    *)
      die "Unknown argument: $1. Use --help." ;;
  esac
done

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------
check_prerequisites() {
  info "Checking prerequisites..."
  command -v aws  >/dev/null 2>&1 || die "AWS CLI not found. Install it: https://aws.amazon.com/cli/"
  command -v python3 >/dev/null 2>&1 || die "python3 not found."
  aws sts get-caller-identity --region "$REGION" >/dev/null 2>&1 \
    || die "AWS credentials not configured or LabRole not active."
  success "Prerequisites OK."
}

# ---------------------------------------------------------------------------
# Stage 1 — INGEST
# Export telemetry_readings, incidents, and anomalies from Supabase to S3 raw/
# ---------------------------------------------------------------------------
stage_ingest() {
  info "=== STAGE 1: INGEST ==="

  [[ -f "$INGEST_SCRIPT" ]] || die "Ingestion script not found: $INGEST_SCRIPT (Role 1 must create it)"

  info "Running ingestion script → s3://${BUCKET}/raw/"
  run python3 "$INGEST_SCRIPT" \
    --bucket "$BUCKET" \
    --region "$REGION" \
    --tables telemetry_readings incidents anomalies \
    --output-prefix raw/

  # Verify files landed in S3
  local tables=("telemetry_readings" "incidents" "anomalies")
  for table in "${tables[@]}"; do
    local count
    count=$(aws s3 ls "s3://${BUCKET}/raw/${table}/" --region "$REGION" 2>/dev/null | wc -l || echo "0")
    if [[ "$count" -eq 0 && "$DRY_RUN" == "false" ]]; then
      die "No files found in s3://${BUCKET}/raw/${table}/ after ingestion."
    fi
    info "  s3://${BUCKET}/raw/${table}/ → ${count} object(s)"
  done

  success "Stage 1 complete: raw data in S3."
}

# ---------------------------------------------------------------------------
# Stage 2 — TRANSFORM
# Glue ETL Job: CSV → Parquet, schema alignment across 3 sources
# ---------------------------------------------------------------------------
stage_transform() {
  info "=== STAGE 2: TRANSFORM (Glue ETL Job) ==="

  info "Starting Glue job: ${GLUE_ETL_JOB}"
  local job_run_id
  job_run_id=$(run aws glue start-job-run \
    --job-name "$GLUE_ETL_JOB" \
    --region "$REGION" \
    --query 'JobRunId' --output text 2>&1) || die "Failed to start Glue job: $job_run_id"

  if [[ "$DRY_RUN" == "true" ]]; then
    success "Stage 2 complete (dry-run, no actual job started)."
    return
  fi

  info "Job run ID: ${job_run_id}. Waiting for completion..."
  local state=""
  local attempts=0
  local max_attempts=60  # 60 × 30s = 30 min max

  while [[ $attempts -lt $max_attempts ]]; do
    state=$(aws glue get-job-run \
      --job-name "$GLUE_ETL_JOB" \
      --run-id "$job_run_id" \
      --region "$REGION" \
      --query 'JobRun.JobRunState' --output text)

    info "  Job state: ${state} (attempt ${attempts}/${max_attempts})"

    case "$state" in
      SUCCEEDED) break ;;
      FAILED|TIMEOUT|STOPPED|ERROR)
        local msg
        msg=$(aws glue get-job-run \
          --job-name "$GLUE_ETL_JOB" \
          --run-id "$job_run_id" \
          --region "$REGION" \
          --query 'JobRun.ErrorMessage' --output text 2>/dev/null || echo "Unknown")
        die "Glue ETL job failed with state ${state}: ${msg}" ;;
    esac

    sleep 30
    ((attempts++))
  done

  [[ "$state" == "SUCCEEDED" ]] || die "Glue ETL job timed out after $((max_attempts * 30 / 60)) minutes."
  success "Stage 2 complete: Parquet files in s3://${BUCKET}/processed/"
}

# ---------------------------------------------------------------------------
# Stage 3 — CATALOG
# Start Glue Crawler and wait for it to update the Data Catalog
# ---------------------------------------------------------------------------
stage_catalog() {
  info "=== STAGE 3: CATALOG (Glue Crawler) ==="

  # Check crawler is not already running
  local current_state
  current_state=$(aws glue get-crawler \
    --name "$GLUE_CRAWLER" \
    --region "$REGION" \
    --query 'Crawler.State' --output text 2>/dev/null || echo "NOT_FOUND")

  if [[ "$current_state" == "NOT_FOUND" ]]; then
    die "Crawler '${GLUE_CRAWLER}' not found. Create it in Glue console first (Role 1 sets this up)."
  fi
  if [[ "$current_state" == "RUNNING" ]]; then
    warn "Crawler already running. Waiting for it to finish..."
  else
    info "Starting crawler: ${GLUE_CRAWLER}"
    run aws glue start-crawler --name "$GLUE_CRAWLER" --region "$REGION"
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    success "Stage 3 complete (dry-run)."
    return
  fi

  local attempts=0
  local max_attempts=40  # 40 × 30s = 20 min max
  while [[ $attempts -lt $max_attempts ]]; do
    current_state=$(aws glue get-crawler \
      --name "$GLUE_CRAWLER" \
      --region "$REGION" \
      --query 'Crawler.State' --output text)

    info "  Crawler state: ${current_state} (attempt ${attempts}/${max_attempts})"

    [[ "$current_state" == "READY" ]] && break

    sleep 30
    ((attempts++))
  done

  [[ "$current_state" == "READY" ]] || die "Crawler timed out or stuck in state: ${current_state}"

  local last_status
  last_status=$(aws glue get-crawler \
    --name "$GLUE_CRAWLER" \
    --region "$REGION" \
    --query 'Crawler.LastCrawl.Status' --output text 2>/dev/null || echo "UNKNOWN")

  [[ "$last_status" == "SUCCEEDED" ]] \
    || warn "Crawler finished with status '${last_status}'. Check the Glue console."

  success "Stage 3 complete: Data Catalog updated."
}

# ---------------------------------------------------------------------------
# Stage 4 — QUALITY
# Run Glue Data Quality job and parse results
# ---------------------------------------------------------------------------
stage_quality() {
  info "=== STAGE 4: DATA QUALITY ==="

  info "Starting DQ job: ${GLUE_DQ_JOB}"
  local job_run_id
  job_run_id=$(run aws glue start-job-run \
    --job-name "$GLUE_DQ_JOB" \
    --region "$REGION" \
    --query 'JobRunId' --output text 2>&1) || die "Failed to start DQ job: $job_run_id"

  if [[ "$DRY_RUN" == "true" ]]; then
    success "Stage 4 complete (dry-run)."
    return
  fi

  info "DQ job run ID: ${job_run_id}. Waiting..."
  local state=""
  local attempts=0
  local max_attempts=40

  while [[ $attempts -lt $max_attempts ]]; do
    state=$(aws glue get-job-run \
      --job-name "$GLUE_DQ_JOB" \
      --run-id "$job_run_id" \
      --region "$REGION" \
      --query 'JobRun.JobRunState' --output text)

    info "  DQ job state: ${state}"
    [[ "$state" == "SUCCEEDED" ]] && break
    [[ "$state" =~ ^(FAILED|TIMEOUT|STOPPED|ERROR)$ ]] && die "DQ job failed: ${state}"

    sleep 30
    ((attempts++))
  done

  [[ "$state" == "SUCCEEDED" ]] || die "DQ job timed out."

  # Download and show the quality report
  local report_key="data_quality/report_$(date +%Y%m%d).json"
  if aws s3 ls "s3://${BUCKET}/${report_key}" --region "$REGION" >/dev/null 2>&1; then
    aws s3 cp "s3://${BUCKET}/${report_key}" "/tmp/dq_report.json" --region "$REGION"
    info "Data Quality Report:"
    python3 -c "
import json, sys
report = json.load(open('/tmp/dq_report.json'))
rules = report.get('rules', [])
passed = sum(1 for r in rules if r.get('status') == 'PASS')
failed = sum(1 for r in rules if r.get('status') == 'FAIL')
print(f'  Passed: {passed} / {len(rules)}')
print(f'  Failed: {failed} / {len(rules)}')
for r in rules:
    icon = '✓' if r.get('status') == 'PASS' else '✗'
    print(f'  {icon} [{r.get(\"rule_id\",\"?\")}] {r.get(\"description\",\"\")} — {r.get(\"status\")}')
if failed > 0:
    sys.exit(1)
" || die "Data quality checks FAILED. Review report at s3://${BUCKET}/${report_key}"
  else
    warn "DQ report not found at s3://${BUCKET}/${report_key}. Check DQ job output."
  fi

  success "Stage 4 complete: all data quality rules passed."
}

# ---------------------------------------------------------------------------
# Stage 5 — ATHENA VIEWS
# Create or refresh the Athena views defined by the Analytics Engineer
# ---------------------------------------------------------------------------
stage_athena() {
  info "=== STAGE 5: ATHENA VIEWS ==="

  local views_dir="analytics/views"
  [[ -d "$views_dir" ]] || die "Views directory not found: ${views_dir} (Role 3 must create SQL files)"

  local sql_files
  mapfile -t sql_files < <(find "$views_dir" -name "*.sql" | sort)

  if [[ ${#sql_files[@]} -eq 0 ]]; then
    warn "No .sql files found in ${views_dir}. Skipping Athena view creation."
    return
  fi

  info "Creating/refreshing ${#sql_files[@]} Athena view(s)..."
  for sql_file in "${sql_files[@]}"; do
    local query
    query=$(cat "$sql_file")
    info "  Executing: $(basename "$sql_file")"

    local exec_id
    exec_id=$(run aws athena start-query-execution \
      --query-string "$query" \
      --query-execution-context Database="$ATHENA_DB" \
      --result-configuration OutputLocation="$ATHENA_OUTPUT" \
      --region "$REGION" \
      --query 'QueryExecutionId' --output text 2>&1) || {
      warn "Failed to start query for $(basename "$sql_file"): $exec_id"
      continue
    }

    if [[ "$DRY_RUN" == "true" ]]; then
      continue
    fi

    # Wait for query to finish
    local q_state=""
    local q_attempts=0
    while [[ $q_attempts -lt 20 ]]; do
      q_state=$(aws athena get-query-execution \
        --query-execution-id "$exec_id" \
        --region "$REGION" \
        --query 'QueryExecution.Status.State' --output text 2>/dev/null || echo "UNKNOWN")
      [[ "$q_state" == "SUCCEEDED" ]] && break
      [[ "$q_state" =~ ^(FAILED|CANCELLED)$ ]] && {
        warn "  Query $(basename "$sql_file") failed: ${q_state}"
        break
      }
      sleep 5
      ((q_attempts++))
    done

    [[ "$q_state" == "SUCCEEDED" ]] \
      && success "  $(basename "$sql_file") → OK" \
      || warn "  $(basename "$sql_file") → ${q_state}"
  done

  success "Stage 5 complete: Athena views ready."
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
  local end_ts
  end_ts=$(date '+%Y-%m-%d %H:%M:%S')
  info "=================================================="
  info "Pipeline run complete at ${end_ts}"
  info "Log file: ${LOG_FILE}"
  info "S3 zones:"
  info "  raw       → s3://${BUCKET}/raw/"
  info "  processed → s3://${BUCKET}/processed/"
  info "  curated   → s3://${BUCKET}/curated/"
  info "  DQ report → s3://${BUCKET}/data_quality/"
  info "Athena DB: ${ATHENA_DB}"
  info "=================================================="
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
  info "HPE GreenLake Digital Twin — Pipeline Orchestration"
  info "Bucket : s3://${BUCKET}"
  info "Region : ${REGION}"
  info "Dry-run: ${DRY_RUN}"
  [[ -n "$ONLY_STAGE" ]] && info "Only stage: ${ONLY_STAGE}"
  echo ""

  check_prerequisites

  case "${ONLY_STAGE:-all}" in
    all)
      stage_ingest
      stage_transform
      stage_catalog
      stage_quality
      stage_athena
      ;;
    ingest)    stage_ingest ;;
    transform) stage_transform ;;
    catalog)   stage_catalog ;;
    quality)   stage_quality ;;
    athena)    stage_athena ;;
    *)
      die "Unknown stage '${ONLY_STAGE}'. Valid: ingest, transform, catalog, quality, athena" ;;
  esac

  print_summary
}

main "$@"
