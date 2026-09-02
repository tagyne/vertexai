"""Local model construction and training."""

from pathlib import Path
import json

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from src.data import CATEGORICAL_FEATURES, NUMERICAL_FEATURES


def build_preprocessor() -> ColumnTransformer:
    return ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("numerical", "passthrough", NUMERICAL_FEATURES),
        ],
        remainder="drop",
    )


def build_model(random_state: int = 42, n_estimators: int = 100) -> Pipeline:
    return Pipeline(
        [
            ("preprocessor", build_preprocessor()),
            ("regressor", RandomForestRegressor(
                n_estimators=n_estimators, random_state=random_state, n_jobs=-1,
            )),
        ]
    )


def train_model(features: pd.DataFrame, target: pd.Series, output_dir: str | Path) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    model = build_model()
    model.fit(features, target)
    model_path = output_path / "model.joblib"
    joblib.dump(model, model_path)
    metadata = {"model_path": str(model_path), "feature_names": list(features.columns)}
    (output_path / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata
