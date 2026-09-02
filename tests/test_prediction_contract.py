import pytest

from src.predict import parse_prediction_request, format_prediction_response


def test_prediction_request_requires_all_raw_features() -> None:
    with pytest.raises(ValueError, match="Missing prediction features"):
        parse_prediction_request({"instances": [{"gender": "Female"}]})


def test_prediction_contract_round_trips_instances_and_response() -> None:
    instance = {
        "gender": "Female", "study_time_hours": 4.0, "attendance_percent": 88.0,
        "sleep_hours": 7.0, "parental_education": "Bachelors", "internet_access": "Yes",
        "extracurricular_activities": "Yes", "part_time_job": "No", "previous_grade": 76.9,
    }

    assert parse_prediction_request({"instances": [instance]}) == [instance]
    assert format_prediction_response([76.4]) == {"predictions": [{"predicted_final_exam_score": 76.4}]}
