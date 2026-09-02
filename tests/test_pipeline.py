from pathlib import Path

from kfp import compiler

from src.pipeline import student_performance_pipeline


def test_pipeline_definition_compiles(tmp_path: Path) -> None:
    output = tmp_path / "pipeline.yaml"

    compiler.Compiler().compile(student_performance_pipeline, str(output))

    assert output.exists()
    assert output.stat().st_size > 0


def test_pipeline_contains_one_component_per_stage(tmp_path: Path) -> None:
    output = tmp_path / "pipeline.yaml"

    compiler.Compiler().compile(student_performance_pipeline, str(output))
    pipeline_text = output.read_text(encoding="utf-8")

    for component_name in (
        "download-dataset", "prepare-data", "train-model", "evaluate-model",
        "register-model", "deploy-model",
    ):
        assert component_name in pipeline_text
