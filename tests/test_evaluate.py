from src.evaluate import regression_metrics


def test_regression_metrics_returns_mae_and_rmse() -> None:
    metrics = regression_metrics([1.0, 3.0], [2.0, 5.0])

    assert metrics["mae"] == 1.5
    assert metrics["rmse"] == 1.5811388300841898
