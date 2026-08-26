# Last run: Wed Aug 26 07:24:37 UTC 2026
# Load Packages
import requests
import pandas as pd
from datetime import datetime
from google.cloud import bigquery
from io import BytesIO

GSAF_URL = "https://sharkattackfile.net/spreadsheets/GSAF5.xls"
PROJECT_ID = "data-storage-485106"
DATASET = "sharks"


def fetch_raw_data():
    """Download the raw GSAF spreadsheet as bytes.

    GSAF publishes the FULL global shark attack history in one file every
    time -- there's no incremental/delta version of this source. That fact
    is what makes the rest of this pipeline simple: we never need to merge
    old data with new data, because 'new' already contains everything.
    """
    response = requests.get(GSAF_URL, timeout=30)
    response.raise_for_status()  # fail loudly and fast if GSAF is down or returns an error page
    return BytesIO(response.content)  # in-memory file object, no disk write needed


def transform(raw_file):
    """Clean and normalize the raw spreadsheet into a tidy dataframe."""
    df = pd.read_excel(raw_file)

    # These columns are known junk in GSAF's export: leftover duplicate
    # index columns and empty "Unnamed" columns caused by merged cells in
    # the source spreadsheet. Only dropped if present, so this doesn't
    # break if GSAF ever removes them upstream.
    junk_cols = ["Case Number.1", "original order", "Unnamed: 21", "Unnamed: 22"]
    df = df.drop(columns=[c for c in junk_cols if c in df.columns])

    # Normalize column names: "Case Number" -> "case_number", etc.
    # Keeps downstream SQL/dbt references predictable and consistent.
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("/", "_")
    )

    # Replace missing values with an explicit "unknown" string rather than
    # leaving nulls -- makes gaps visible/queryable instead of silently
    # dropped or NaN.
    df = df.fillna("unknown")

    # Cast everything to string. This is a deliberate simplification: it
    # avoids type-inference issues from GSAF's messy/inconsistent source
    # formatting (dates, numbers mixed with text), at the cost of losing
    # native types in BigQuery. Anything doing numeric/date logic later
    # (e.g. filtering by year, parsing date) will need an explicit CAST
    # in SQL downstream.
    df = df.astype(str)
    return df


def validate(df):
    """Cheap sanity checks before writing anything to BigQuery.

    Protects against a silently broken source: if GSAF changes their
    spreadsheet structure, renames a column, or serves an error page
    instead of the real file, these asserts catch it here instead of
    letting bad/empty data overwrite a good table.
    """
    assert len(df) > 0, "No rows after transform — source may be empty or format changed"
    assert "date" in df.columns, "Missing date column"
    assert "location" in df.columns, "Missing location column"
    assert "year" in df.columns, "Missing year column"


def get_schema(df):
    """Build an explicit BigQuery schema, every column as STRING.

    Passing this explicitly (rather than letting BigQuery autodetect from
    the dataframe) guarantees a new monthly table gets created with a
    predictable, consistent schema every time -- no surprises from
    autodetect guessing a different type in a future run.
    """
    return [bigquery.SchemaField(col, "STRING") for col in df.columns]


def write_snapshot(df, client, table_id):
    """Idempotent by construction: GSAF is always the full authoritative
    dataset, so every run fully replaces the table with a fresh source
    read. Rerun any number of times, same input always produces the same
    output. No DML needed, no merge logic needed — WRITE_TRUNCATE against
    a fresh fetch is sufficient because the source itself has no concept
    of 'incremental'.

    WRITE_TRUNCATE also handles table creation implicitly: if table_id
    doesn't exist yet (e.g. it's the 1st of a new month), the load job
    creates it fresh using the schema provided below. If it already
    exists, WRITE_TRUNCATE just overwrites its contents. Either way, no
    explicit CREATE TABLE step is needed anywhere in this pipeline.
    """
    schema = get_schema(df)
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE", schema=schema)
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # blocks until the load job finishes, so failures surface here, not silently
    print(f"Idempotent load completed into {table_id}, total rows: {len(df)}")


def run():
    now = datetime.now()

    # Table name rolls over automatically based on the current month,
    # e.g. attacks_2026_sep. No special-casing needed for "new month" --
    # the string just changes, and write_snapshot() creates it on demand.
    # This also naturally sidesteps BigQuery sandbox's 60-day table
    # expiry: each monthly table gets written to regularly within its
    # own month, and old months are left to expire on their own since
    # each new month's table already contains the full history anyway.
    table_suffix = f"{now.year}_{now.strftime('%b').lower()}"  # e.g. 2026_sep
    table_id = f"{PROJECT_ID}.{DATASET}.attacks_{table_suffix}"
    client = bigquery.Client(project=PROJECT_ID)

    # Straight-line path, same every day of the month: fetch -> clean ->
    # validate -> write. No day-of-month branching, no carry-forward from
    # previous tables -- the source already gives us everything we need
    # in one fetch.
    raw = fetch_raw_data()
    bigdata = transform(raw)
    validate(bigdata)
    write_snapshot(bigdata, client, table_id)

    print(f"Shark attacks data of shape {bigdata.shape} has been successfully retrieved, saved, and loaded to the BigQuery table.")


if __name__ == "__main__":
    run()
