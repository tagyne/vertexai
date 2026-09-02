import pandas as pd

from src.data import CATEGORICAL_FEATURES, NUMERICAL_FEATURES, TARGET_COLUMN, prepare_dataset


def test_prepare_dataset_excludes_identifiers_target_and_leakage() -> None:
    frame = pd.DataFrame(
        {
            "student_id": [1], "gender": ["Female"], "study_time_hours": [4.0],
            "attendance_percent": [88.0], "sleep_hours": [7.0],
            "parental_education": ["Bachelors"], "internet_access": ["Yes"],
            "extracurricular_activities": ["Yes"], "part_time_job": ["No"],
            "previous_grade": [76.9], "final_exam_score": [76.4], "final_grade": ["A"],
        }
    )

    features, target = prepare_dataset(frame)

    assert list(features.columns) == CATEGORICAL_FEATURES + NUMERICAL_FEATURES
    assert "student_id" not in features
    assert "final_grade" not in features
    assert target.name == TARGET_COLUMN


def test_prepare_dataset_rejects_missing_required_columns() -> None:
    with __import__("pytest").raises(ValueError, match="Missing required columns"):
        prepare_dataset(pd.DataFrame({"final_exam_score": [1.0]}))
