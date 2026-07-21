import requests
import pandas as pd
from google.cloud import bigquery
from io import BytesIO

GSAF_URL = "https://sharkattackfile.net/spreadsheets/GSAF5.xls"
PROJECT_ID = "data-storage-485106"  # reuse your existing project
DATASET = "sharks"
TABLE_ID = f"{PROJECT_ID}.{DATASET}.attacks"


def fetch_raw_data():
    response = requests.get(GSAF_URL, timeout=30)
    response.raise_for_status()
    return BytesIO(response.content)


def transform(raw_file):
    df = pd.read_excel(raw_file)

    # Drop genuine junk columns
    junk_cols = ["Case Number.1", "original order", "Unnamed: 21", "Unnamed: 22"]
    df = df.drop(columns=[c for c in junk_cols if c in df.columns])

    # Clean column names: lowercase, underscores
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
    )

    # Standardize date: handle both text ("23rd June") and real datetime objects
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed")

    # Consistent blank handling: fill text columns' blanks with "unknown"
    text_cols = df.select_dtypes(include=["object", "str"]).columns
    df[text_cols] = df[text_cols].fillna("unknown")

    return df


def validate(df):
    assert len(df) > 0, "No rows after transform — source may be empty or format changed"
    assert "date" in df.columns, "Missing date column"
    assert "location" in df.columns, "Missing location column"
    non_null_dates = df["date"].notna().sum()
    assert non_null_dates > len(df) * 0.9, f"Too many unparseable dates: {non_null_dates}/{len(df)} parsed"


def load_to_bigquery(df):
    client = bigquery.Client(project=PROJECT_ID)
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_dataframe(df, TABLE_ID, job_config=job_config)
    job.result()
    print(f"Loaded {len(df)} rows into {TABLE_ID}")


if __name__ == "__main__":
    raw = fetch_raw_data()
    data = transform(raw)
    validate(data)
    load_to_bigquery(data)
