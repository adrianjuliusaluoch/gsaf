import sys
from pathlib import Path
import pytest
import pandas as pd
from unittest.mock import MagicMock

# Make fetch_and_load.py importable from the repo root, since tests/ is a
# subfolder. Without this, pytest can fail to find the module depending on
# how/where it's invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

FIXTURES_DIR = Path(__file__).resolve().parent / "tests" / "fixtures"


@pytest.fixture
def real_sample_path():
    """Path to a real, one-time-downloaded GSAF spreadsheet.

    This is committed to the repo (not fetched live in CI) so tests never
    depend on network access or GSAF's uptime. Refresh this file
    occasionally by hand if you want tests to reflect any drift in
    GSAF's real-world formatting over time.
    """
    path = FIXTURES_DIR / "gsaf_real_sample.xls"
    if not path.exists():
        pytest.skip(
            f"Real fixture not found at {path}. "
            "Download GSAF5.xls once and save it there to enable this test."
        )
    return path


@pytest.fixture
def empty_df():
    """A dataframe with no rows -- should trip validate()'s row-count check."""
    return pd.DataFrame(columns=["date", "location", "year"])


@pytest.fixture
def df_missing_date():
    """Has location and year, but no date column -- should trip validate()."""
    return pd.DataFrame({"location": ["Bahamas"], "year": ["2026"]})


@pytest.fixture
def df_missing_location():
    """Has date and year, but no location column -- should trip validate()."""
    return pd.DataFrame({"date": ["2026-01-01"], "year": ["2026"]})


@pytest.fixture
def df_missing_year():
    """Has date and location, but no year column -- should trip validate()."""
    return pd.DataFrame({"date": ["2026-01-01"], "location": ["Bahamas"]})


@pytest.fixture
def mock_bq_client():
    """A fake bigquery.Client that records how it was called instead of
    hitting real GCP. load_table_from_dataframe() normally returns a job
    object with a .result() method that blocks until the load finishes --
    we mock that shape so write_snapshot() runs unmodified against it.
    """
    client = MagicMock()
    fake_job = MagicMock()
    fake_job.result.return_value = None  # simulate a load job that "completes" instantly
    client.load_table_from_dataframe.return_value = fake_job
    return client
