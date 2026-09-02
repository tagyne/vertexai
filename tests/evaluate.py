"""Local evaluation helpers used by tests and experiments."""

import json
import math
from pathlib import Path
from typing import Iterable


def regression_metrics(actual: Iterable[float], predicted: Iterable[float]) -> dict[str, float]:
    actual_values = list(actual)
    predicted_values = list(predicted)
    if not actual_values or len(actual_values) != len(predicted_values):
        raise ValueError("Actual and predicted values must have the same non-zero length")
    errors = [prediction - value for value, prediction in zip(actual_values, predicted_values)]
    return {
        "mae": sum(abs(error) for error in errors) / len(errors),
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
    }


def save_metrics(metrics: dict[str, float], output_path: str | Path) -> None:
    Path(output_path).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
