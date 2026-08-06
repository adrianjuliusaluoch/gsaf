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

now = datetime.now()
table_suffix = f"{now.year}_{now.strftime('%b').lower()}"  # e.g. 2026_aug
table_id = f"{PROJECT_ID}.{DATASET}.attacks_{table_suffix}"

client = bigquery.Client(project=PROJECT_ID)


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


def create_table_if_missing(df):
    try:
        client.get_table(table_id)
    except NotFound:
        schema = get_schema(df)
        table = bigquery.Table(table_id, schema=schema)
        client.create_table(table)
        print(f"Created new monthly table: {table_id}")


def write_snapshot(df):
    create_table_if_missing(df)
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    print(f"Load completed into {table_id}, rows: {len(df)}")


bigdata = None

if now.day == 1 or now.day == 2:
    try:
        check_sql = f"SELECT COUNT(*) AS cnt FROM `{table_id}`"
        check_df = client.query(check_sql).to_dataframe()
        has_current_month_data = check_df.loc[0, "cnt"] > 0
    except NotFound:
        has_current_month_data = False  # Table doesn't exist yet

    raw = fetch_raw_data()
    bigdata = transform(raw)
    validate(bigdata)

    if not has_current_month_data:
        try:
            prev_month_date = now.replace(day=1) - timedelta(days=1)
            prev_table_suffix = f"{prev_month_date.year}_{prev_month_date.strftime('%b').lower()}"
            prev_table_id = f"{PROJECT_ID}.{DATASET}.attacks_{prev_table_suffix}"

            try:
                prev_data = client.query(f"SELECT * FROM `{prev_table_id}`").to_dataframe()
                bigdata = pd.concat([prev_data, bigdata], ignore_index=True)
                print(f"Appended {len(prev_data)} rows from previous month table.")
            except NotFound:
                print("No previous month table found, skipping carry-forward.")

            if "case_number" in bigdata.columns:
                bigdata.drop_duplicates(subset=["case_number"], keep="last", inplace=True)
            else:
                bigdata.drop_duplicates(keep="last", inplace=True)

        except Exception as e:
            print(f"Error during carry-forward from previous month: {e}")

    write_snapshot(bigdata)

else:
    raw = fetch_raw_data()
    bigdata = transform(raw)
    validate(bigdata)
    write_snapshot(bigdata)

print(f"Shark attacks data of shape {bigdata.shape} has been successfully retrieved, saved, and loaded to the BigQuery table.")
