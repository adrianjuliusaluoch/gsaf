"""
Lightweight, sandbox-safe replacement for Elementary.

Elementary's checks all depend on persisted historical state (snapshots,
incrementals) which compile to MERGE -- DML that BigQuery sandbox blocks
without billing. This module gets the same *information* a different way:
every run appends one row to a log table via WRITE_APPEND (a load-job
setting, not DML -- same mechanism fetch_and_load.py already relies on
for WRITE_TRUNCATE). Freshness, schema-change, and anomaly checks are
then just plain SELECT queries against that log table -- fully read-only,
no DML anywhere.
"""

from datetime import datetime, timezone
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

LOG_TABLE = "data-storage-485106.sharks.pipeline_observability"


def get_run_metrics(df, table_id):
    """Compute this run's metrics -- the same facts Elementary would have
    tracked, just gathered directly from the dataframe we already have in
    memory instead of querying BigQuery after the fact.
    """
    return {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "table_id": table_id,
        "row_count": len(df),
        "column_count": len(df.columns),
        # Sorted + joined so it's a stable, comparable string across runs --
        # two runs with the same columns in a different order should still
        # count as "no schema change".
        "columns": ",".join(sorted(df.columns)),
    }


def get_previous_run(client):
    """Fetch the most recent previously-logged run, if any. Read-only
    SELECT -- no DML, safe in sandbox. Returns None if this is the very
    first run (log table doesn't exist yet, or is empty).
    """
    query = f"""
        SELECT row_count, columns, run_timestamp
        FROM `{LOG_TABLE}`
        ORDER BY run_timestamp DESC
        LIMIT 1
    """
    try:
        rows = list(client.query(query).result())
        return rows[0] if rows else None
    except NotFound:
        return None


def get_recent_row_counts(client, n=7):
    """Row counts from the last n runs, for the anomaly check. Read-only,
    same pattern as get_previous_run().
    """
    query = f"""
        SELECT row_count
        FROM `{LOG_TABLE}`
        ORDER BY run_timestamp DESC
        LIMIT {n}
    """
    try:
        return [row.row_count for row in client.query(query).result()]
    except NotFound:
        return []


def check_schema_change(current_columns, previous_run):
    """Flags if this run's column set differs from the last logged run --
    the same signal Elementary's schema_columns_snapshot was providing.
    """
    if previous_run is None:
        return False, "No previous run to compare against (first run)."
    if current_columns != previous_run.columns:
        return True, (
            f"Schema changed since last run.\n"
            f"  Previous: {previous_run.columns}\n"
            f"  Current:  {current_columns}"
        )
    return False, "Schema unchanged."


def check_row_count_anomaly(current_count, recent_counts, threshold_pct=10):
    """Flags if this run's row count deviates from the recent average by
    more than threshold_pct -- the same idea as Elementary's anomaly
    detection, just a hand-rolled version of it.
    """
    if not recent_counts:
        return False, "No history yet to compare against (first run)."
    avg = sum(recent_counts) / len(recent_counts)
    if avg == 0:
        return False, "Average of recent runs is zero, skipping anomaly check."
    deviation_pct = abs(current_count - avg) / avg * 100
    if deviation_pct > threshold_pct:
        return True, (
            f"Row count anomaly: current={current_count}, "
            f"recent_avg={avg:.0f}, deviation={deviation_pct:.1f}% "
            f"(threshold={threshold_pct}%)"
        )
    return False, f"Row count within normal range (deviation={deviation_pct:.1f}%)."


def log_run(client, metrics):
    """Append this run's metrics to the log table. WRITE_APPEND on a load
    job -- not DML -- so this is safe in sandbox. Creates the table on
    first run since a schema is provided explicitly.
    """
    schema = [
        bigquery.SchemaField("run_timestamp", "TIMESTAMP"),
        bigquery.SchemaField("table_id", "STRING"),
        bigquery.SchemaField("row_count", "INTEGER"),
        bigquery.SchemaField("column_count", "INTEGER"),
        bigquery.SchemaField("columns", "STRING"),
    ]
    job_config = bigquery.LoadJobConfig(write_disposition="WRITE_APPEND", schema=schema)
    job = client.load_table_from_json([metrics], LOG_TABLE, job_config=job_config)
    job.result()
    print(f"Logged observability metrics for {metrics['table_id']}, row_count={metrics['row_count']}")


def run_observability_checks(df, client, table_id):
    """Entry point -- call this from fetch_and_load.py right after
    write_snapshot(). Runs all checks, logs the run, and prints results.
    Doesn't raise on anomalies by default (freshness/schema/anomaly
    issues are worth knowing about, not necessarily worth failing the
    whole pipeline over) -- but the print output shows clearly in the
    GitHub Actions log either way.
    """
    metrics = get_run_metrics(df, table_id)
    previous_run = get_previous_run(client)
    recent_counts = get_recent_row_counts(client)

    schema_changed, schema_msg = check_schema_change(metrics["columns"], previous_run)
    anomaly_found, anomaly_msg = check_row_count_anomaly(metrics["row_count"], recent_counts)

    print("--- Observability checks ---")
    print(f"Schema check:      {'FLAGGED' if schema_changed else 'OK'} -- {schema_msg}")
    print(f"Row count check:   {'FLAGGED' if anomaly_found else 'OK'} -- {anomaly_msg}")
    print("----------------------------")

    log_run(client, metrics)

    return {
        "schema_changed": schema_changed,
        "anomaly_found": anomaly_found,
    }
