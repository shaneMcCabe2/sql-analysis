"""Run the BQ->BQ transfer: copy a filtered slice of the public Stack Overflow
dataset into this project's `raw` landing dataset.

Executes every sql/transfer/*.sql file in filename order. Each file is a
CREATE OR REPLACE TABLE, so the run is idempotent -- safe to re-run.

Usage:
    python -m ingest.transfer            # run all transfer files
    python -m ingest.transfer --dry-run  # estimate bytes scanned, write nothing
"""

from __future__ import annotations

import argparse
from pathlib import Path

from google.cloud import bigquery

from ingest.config import bq_client, settings

TRANSFER_DIR = Path(__file__).resolve().parent.parent / "sql" / "transfer"


def ensure_raw_dataset(client: bigquery.Client) -> None:
    ds = bigquery.Dataset(f"{settings.project_id}.{settings.bq_raw_dataset}")
    ds.location = settings.bq_location
    client.create_dataset(ds, exists_ok=True)
    print(f"dataset ready: {settings.project_id}.{settings.bq_raw_dataset}")


def run(dry_run: bool) -> None:
    client = bq_client()
    if not dry_run:
        ensure_raw_dataset(client)

    files = sorted(TRANSFER_DIR.glob("*.sql"))
    if not files:
        raise SystemExit(f"no .sql files found in {TRANSFER_DIR}")

    total_gb = 0.0
    for path in files:
        sql = path.read_text()
        job = client.query(
            sql, job_config=bigquery.QueryJobConfig(dry_run=dry_run)
        )
        if dry_run:
            gb = job.total_bytes_processed / 1e9
            total_gb += gb
            print(f"[dry-run] {path.name:<20} would scan {gb:6.2f} GB")
        else:
            job.result()  # wait
            gb = (job.total_bytes_processed or 0) / 1e9
            total_gb += gb
            print(f"[done]    {path.name:<20} scanned {gb:6.2f} GB")

    label = "would scan" if dry_run else "scanned"
    print(f"\nTotal {label}: {total_gb:.2f} GB "
          f"(BigQuery free tier = 1000 GB/month).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="estimate bytes scanned without writing tables")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
