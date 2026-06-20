"""Shared configuration and BigQuery client factory.

Reads settings from the project .env (see .env.example). Import `settings`
for config values and `bq_client()` for an authenticated client.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the repo root regardless of where the script is run from.
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    project_id: str
    credentials_path: str
    bq_location: str
    bq_raw_dataset: str


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var {name!r}. See .env.example.")
    return value


settings = Settings(
    project_id=_require("GCP_PROJECT_ID"),
    credentials_path=_require("GOOGLE_APPLICATION_CREDENTIALS"),
    bq_location=os.environ.get("BQ_LOCATION", "US"),
    bq_raw_dataset=os.environ.get("BQ_RAW_DATASET", "raw"),
)


def bq_client():
    """Return an authenticated BigQuery client scoped to the configured project."""
    from google.cloud import bigquery

    return bigquery.Client(
        project=settings.project_id, location=settings.bq_location
    )
