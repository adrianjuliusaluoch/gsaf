# Load Packages
import pandas as pd
import pytest
from fetch_and_load import transform, validate


def make_sample_excel(tmp_path):
    """Hand-crafted synthetic data mimicking real GSAF messiness: mixed
    date formats, a mixed-type Age column ('20's', '?', ints), scattered
    nulls, and the actual junk columns GSAF's export carries. Used for
    fast, fully-controlled tests of transform()'s cleaning logic -- we
    know exactly what's "wrong" going in, so we can assert exactly what
    should come out.
    """
    df = pd.DataFrame({
        "Date": ["23rd June", pd.Timestamp("2025-06-11"), "13th June", "1st June", pd.Timestamp("2024-11-04")],
        "Year": [2026, 2025, 2026, 2026, 2024],
        "Type": ["Unprovoked", "Unprovoked", "Provoked", "Unprovoked", "Unprovoked"],
        "Country": ["Bahamas", "USA", "Australia", None, "Brazil"],
        "State": [None, "Florida", "NSW", "Florida", None],
        "Location": ["Exhuma Cays", None, "Coogee Beach", "Pensacola Beach", "Boa Via gem beach"],
        "Activity": ["Swimming", "Swimming", "Swimming", None, "Swimming"],
        "Name": ["Unknown", "Keira Ralph", "Leah Stewart", "Unknown", None],
        "Sex": ["M", "F", "F", "M", "F"],
        "Age": [12, 17, "20's", None, "?"],
        "Injury": ["Not stated", "Bite to back of ankle", "Bite wound to L thigh", "Bite to leg", None],
        "Fatal Y/N": ["N", "N", "N", "N", None],
        "Time": ["1530hrs", "1145hrs", None, "1800hrs", "1643hrs"],
        "Species ": [None, "Unknown small shark", "Great White Shark", "Bull shark", None],
        "Source": ["Keith Cowley", "Keith Cowley", "Simon De Marchi", "Keith Cowley", "Keith Cowley"],
        "pdf": [None, None, None, None, None],
        "href formula": [None, None, None, None, None],
        "href": [None, None, None, None, None],
        "Case Number": [None, None, None, None, "GSAF2024.11.04"],
        "Case Number.1": [None, None, None, None, "2024.11.04"],
        "original order": [1, 2, 3, 4, 5],
        "Unnamed: 21": [None, None, None, None, None],
        "Unnamed: 22": [None, None, None, None, None],
    })
    path = tmp_path / "sample.xlsx"
    df.to_excel(path, index=False)
    return path


# ---------------------------------------------------------------------
# transform() -- synthetic edge cases
# ---------------------------------------------------------------------

def test_junk_columns_dropped(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    assert "case_number.1" not in df.columns
    assert "original_order" not in df.columns


def test_all_columns_are_string(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    assert all(pd.api.types.is_string_dtype(df[col]) for col in df.columns)


def test_mixed_age_values_preserved(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    assert "20's" in df["age"].values
    assert "?" in df["age"].values


def test_blanks_filled(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    assert (df["location"] == "unknown").any()


# ---------------------------------------------------------------------
# transform() -- real downloaded data
# Confirms transform() survives GSAF's actual current export, not just
# our best guess at what it looks like. Skips automatically (via the
# real_sample_path fixture) if the fixture file hasn't been downloaded
# yet, rather than failing the whole suite.
# ---------------------------------------------------------------------

def test_transform_handles_real_data(real_sample_path):
    df = transform(real_sample_path)
    # Same structural guarantees we rely on from validate(), checked here
    # against real data specifically -- proves the real export still has
    # the shape our pipeline expects.
    assert len(df) > 0
    assert "date" in df.columns
    assert "location" in df.columns
    assert "year" in df.columns
    assert "case_number.1" not in df.columns  # junk column actually exists and gets dropped
    assert all(pd.api.types.is_string_dtype(df[col]) for col in df.columns)


def test_validate_passes_on_real_data(real_sample_path):
    df = transform(real_sample_path)
    validate(df)  # should not raise


# ---------------------------------------------------------------------
# validate() -- failure paths
# These are the tests that were missing before: proving validate()
# actually catches bad data, not just that it stays quiet on good data.
# Uses the synthetic "broken" fixtures defined in conftest.py.
# ---------------------------------------------------------------------

def test_validate_raises_on_empty_df(empty_df):
    with pytest.raises(AssertionError, match="No rows"):
        validate(empty_df)


def test_validate_raises_on_missing_date_column(df_missing_date):
    with pytest.raises(AssertionError, match="Missing date column"):
        validate(df_missing_date)


def test_validate_raises_on_missing_location_column(df_missing_location):
    with pytest.raises(AssertionError, match="Missing location column"):
        validate(df_missing_location)


def test_validate_raises_on_missing_year_column(df_missing_year):
    with pytest.raises(AssertionError, match="Missing year column"):
        validate(df_missing_year)
