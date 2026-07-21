import pandas as pd
from fetch_and_load import transform, validate


def make_sample_excel(tmp_path):
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
        "Age": [12, 17, 35, None, 19],
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


def test_junk_columns_dropped(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    assert "case_number.1" not in df.columns
    assert "original_order" not in df.columns


def test_date_parsed(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    assert df["date"].notna().sum() == 5


def test_blanks_filled(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    assert (df["location"] == "unknown").any()


def test_validate_passes(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    validate(df)  # should not raise
