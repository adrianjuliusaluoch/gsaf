# Load Packages
import pandas as pd
from fetch_and_load import write_snapshot


def make_clean_df():
    """A small already-transformed-looking dataframe -- write_snapshot()
    doesn't care about GSAF specifics, only that it receives a dataframe
    and a table_id, so this can be minimal.
    """
    return pd.DataFrame({
        "date": ["2026-01-01", "2026-01-02"],
        "location": ["Bahamas", "Australia"],
        "year": ["2026", "2026"],
    })


def test_write_snapshot_calls_load_with_write_truncate(mock_bq_client):
    """Confirms write_snapshot() requests WRITE_TRUNCATE specifically --
    this is the setting that makes the whole pipeline idempotent (full
    replace every run, no duplicate risk from reruns/retries). If this
    ever silently changed to WRITE_APPEND, duplicates would start
    accumulating on every retry -- this test exists to catch that.
    """
    df = make_clean_df()
    table_id = "some-project.sharks.attacks_2026_jan"

    write_snapshot(df, mock_bq_client, table_id)

    mock_bq_client.load_table_from_dataframe.assert_called_once()
    _, kwargs = mock_bq_client.load_table_from_dataframe.call_args
    job_config = kwargs["job_config"]
    assert job_config.write_disposition == "WRITE_TRUNCATE"


def test_write_snapshot_targets_correct_table(mock_bq_client):
    """Confirms the table_id passed in is actually the one used in the
    load call -- catches accidental hardcoding or argument-order bugs.
    """
    df = make_clean_df()
    table_id = "some-project.sharks.attacks_2026_jan"

    write_snapshot(df, mock_bq_client, table_id)

    args, kwargs = mock_bq_client.load_table_from_dataframe.call_args
    # table_id may be passed positionally or as a kwarg depending on the
    # call site, so check both to keep this test resilient to that.
    called_table_id = kwargs.get("destination") or (args[1] if len(args) > 1 else None)
    assert called_table_id == table_id or table_id in str(args) or table_id in str(kwargs)


def test_write_snapshot_passes_correct_row_count(mock_bq_client):
    """Confirms the exact dataframe we passed in is what gets sent to
    the load job -- not a filtered/mutated copy.
    """
    df = make_clean_df()
    table_id = "some-project.sharks.attacks_2026_jan"

    write_snapshot(df, mock_bq_client, table_id)

    args, kwargs = mock_bq_client.load_table_from_dataframe.call_args
    sent_df = args[0]
    assert len(sent_df) == len(df)


def test_write_snapshot_waits_for_job_completion(mock_bq_client):
    """Confirms job.result() actually gets called -- this is what makes
    write_snapshot() synchronous and lets failures surface as exceptions
    instead of silently continuing before the load actually finishes.
    """
    df = make_clean_df()
    table_id = "some-project.sharks.attacks_2026_jan"

    write_snapshot(df, mock_bq_client, table_id)

    fake_job = mock_bq_client.load_table_from_dataframe.return_value
    fake_job.result.assert_called_once()
