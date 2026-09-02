import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline

from src.train import build_model


def test_build_model_contains_preprocessor_and_random_forest() -> None:
    model = build_model()

    assert isinstance(model, Pipeline)
    assert list(model.named_steps) == ["preprocessor", "regressor"]
    assert isinstance(model.named_steps["regressor"], RandomForestRegressor)
    assert model.named_steps["regressor"].random_state == 42


def test_model_trains_on_raw_contract_columns() -> None:
    model = build_model(n_estimators=5)
    features = pd.DataFrame(
        {
            "gender": ["Female", "Male"], "parental_education": ["Bachelors", "High School"],
            "internet_access": ["Yes", "No"], "extracurricular_activities": ["Yes", "No"],
            "part_time_job": ["No", "Yes"], "study_time_hours": [4.0, 2.0],
            "attendance_percent": [88.0, 70.0], "sleep_hours": [7.0, 6.0],
            "previous_grade": [76.9, 61.0],
        }
    )

    model.fit(features, [76.4, 60.0])

    assert len(model.predict(features)) == 2
