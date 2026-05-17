# Presentation

Place the final slides PDF here:

```
presentation/slides.pdf
```

## Live Demo Checklist (Role 4)

- [ ] AWS Academy lab active and LabRole verified (`aws sts get-caller-identity`)
- [ ] S3 bucket accessible (`aws s3 ls s3://hpe-greenlake-dt-datalake/`)
- [ ] Glue jobs visible in console
- [ ] Glue Crawler ready state
- [ ] Athena database `digital_twin_db` with tables visible
- [ ] QuickSight dashboard loaded and rendering data
- [ ] `run_pipeline.sh --dry-run` executes without errors

## Backup Demo Checklist

- [ ] Docker installed and `docker compose` available
- [ ] `data_samples/` CSVs present
- [ ] `docker compose -f orchestration/docker-compose-local.yml up -d` runs
- [ ] `python3 pipeline/local_pipeline.py --input data_samples/ --output /tmp/output/` succeeds
- [ ] Parquet output readable with pandas
