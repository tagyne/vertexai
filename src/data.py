"""Dataset loading and validation for the student performance contract."""

from pathlib import Path

import pandas as pd

KAGGLE_DATASET_HANDLE = "harshadapatil31/student-performance-and-study-habits-dataset"

IDENTIFIER_COLUMNS = ["student_id"]
CATEGORICAL_FEATURES = [
    "gender", "parental_education", "internet_access",
    "extracurricular_activities", "part_time_job",
]
NUMERICAL_FEATURES = [
    "study_time_hours", "attendance_percent", "sleep_hours", "previous_grade",
]
TARGET_COLUMN = "final_exam_score"
LEAKAGE_COLUMNS = ["final_grade"]
MISSING_CATEGORY = "Unknown"
REQUIRED_COLUMNS = IDENTIFIER_COLUMNS + CATEGORICAL_FEATURES + NUMERICAL_FEATURES + [
    TARGET_COLUMN,
] + LEAKAGE_COLUMNS


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Load a CSV and validate its required schema."""
    return prepare_raw_frame(pd.read_csv(path))


def prepare_raw_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")
    if frame.empty:
        raise ValueError("Dataset must contain at least one row")
    frame[CATEGORICAL_FEATURES] = frame[CATEGORICAL_FEATURES].fillna(MISSING_CATEGORY)
    non_imputable_columns = IDENTIFIER_COLUMNS + NUMERICAL_FEATURES + [TARGET_COLUMN] + LEAKAGE_COLUMNS
    if frame[non_imputable_columns].isna().any().any():
        raise ValueError("Dataset contains missing values in required columns")
    return frame.copy()


def prepare_dataset(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Return raw model features and target, excluding IDs and target leakage."""
    validated = prepare_raw_frame(frame)
    features = validated[CATEGORICAL_FEATURES + NUMERICAL_FEATURES].copy()
    target = validated[TARGET_COLUMN].copy()
    return features, target
