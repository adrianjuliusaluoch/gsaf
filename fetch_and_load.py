# Last run: Wed Aug 12 18:00:48 UTC 2026
# Load Packages
import requests
import pandas as pd
from datetime import datetime, timedelta
from google.cloud import bigquery
from google.api_core.exceptions import NotFound
from io import BytesIO

GSAF_URL = "https://sharkattackfile.net/spreadsheets/GSAF5.xls"
PROJECT_ID = "data-storage-485106"  # reuse your existing project
DATASET = "sharks"


def fetch_raw_data():
    response = requests.get(GSAF_URL, timeout=30)
    response.raise_for_status()
    return BytesIO(response.content)


def transform(raw_file):
    df = pd.read_excel(raw_file)
    junk_cols = ["Case Number.1", "original order", "Unnamed: 21", "Unnamed: 22"]
    df = df.drop(columns=[c for c in junk_cols if c in df.columns])
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
    )
    df = df.fillna("unknown")
    df = df.astype(str)
    return df


def validate(df):
    assert len(df) > 0, "No rows after transform — source may be empty or format changed"
    assert "date" in df.columns, "Missing date column"
    assert "location" in df.columns, "Missing location column"
    assert "year" in df.columns, "Missing year column"


def get_schema(df):
    return [bigquery.SchemaField(col, "STRING") for col in df.columns]


def write_snapshot(df, client, table_id):
    """Idempotent upsert without DML: read existing table (if any), dedupe
    in pandas, then WRITE_TRUNCATE the full result back. Safe to rerun any
    number of times -- existing cases get updated in place, new ones get
    added, nothing duplicates. Avoids MERGE entirely since DML queries are
    blocked on BigQuery's free tier without a linked billing account."""
    try:
        existing = client.query(f"SELECT * FROM `{table_id}`").to_dataframe()
        combined = pd.concat([existing, df], ignore_index=True)
    except NotFound:
        combined = df

    key_col = "case_number" if "case_number" in combined.columns else combined.columns[0]
    combined.drop_duplicates(subset=[key_col], keep="last", inplace=True)

    schema = get_schema(combined)
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE", schema=schema)
    job = client.load_table_from_dataframe(combined, table_id, job_config=job_config)
    job.result()
    print(f"Idempotent load completed into {table_id}, total rows: {len(combined)}")


def run():
    now = datetime.now()
    table_suffix = f"{now.year}_{now.strftime('%b').lower()}"  # e.g. 2026_aug
    table_id = f"{PROJECT_ID}.{DATASET}.attacks_{table_suffix}"
    client = bigquery.Client(project=PROJECT_ID)

    bigdata = None

    if now.day == 1 or now.day == 2:
        raw = fetch_raw_data()
        bigdata = transform(raw)
        validate(bigdata)

        try:
            prev_month_date = now.replace(day=1) - timedelta(days=1)
            prev_table_suffix = f"{prev_month_date.year}_{prev_month_date.strftime('%b').lower()}"
            prev_table_id = f"{PROJECT_ID}.{DATASET}.attacks_{prev_table_suffix}"
            prev_data = client.query(f"SELECT * FROM `{prev_table_id}`").to_dataframe()
            bigdata = pd.concat([prev_data, bigdata], ignore_index=True)
            print(f"Appended {len(prev_data)} rows from previous month table.")
        except NotFound:
            print("No previous month table found, skipping carry-forward.")

        write_snapshot(bigdata, client, table_id)

    else:
        raw = fetch_raw_data()
        bigdata = transform(raw)
        validate(bigdata)
        write_snapshot(bigdata, client, table_id)

    print(f"Shark attacks data of shape {bigdata.shape} has been successfully retrieved, saved, and loaded to the BigQuery table.")


if __name__ == "__main__":
    run()
