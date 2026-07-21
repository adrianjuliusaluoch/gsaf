import pandas as pd
from fetch_and_load import transform, validate


def make_sample_excel(tmp_path):
    df = pd.DataFrame({
        "Date": ["23rd June", pd.Timestamp("2025-06-11")],
        "Year": [2026, 2025],
        "Location": ["Exhuma Cays", None],
        "Name": ["Unknown", "Keira Ralph"],
        "Case Number.1": [None, None],
        "original order": [1, 2],
        "Unnamed: 21": [None, None],
        "Unnamed: 22": [None, None],
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
    assert df["date"].notna().sum() == 2


def test_blanks_filled(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    assert (df["location"] == "unknown").any()


def test_validate_passes(tmp_path):
    path = make_sample_excel(tmp_path)
    df = transform(path)
    validate(df)  # should not raise
