import json

from src.logging import ExperimentLogger, JsonlTrace


def test_experiment_logger_allocates_ids_and_keeps_failures(tmp_path):
    logger = ExperimentLogger(tmp_path / "experiments.jsonl")
    assert logger.next_experiment_id() == "EXP_000001"
    logger.append_experiment(
        {"experiment_id": "EXP_000001", "hamiltonian_id": "HAM_A", "status": "SUCCESS", "configuration": {}}
    )
    logger.append_experiment(
        {
            "experiment_id": "EXP_000002",
            "hamiltonian_id": "HAM_A",
            "status": "FAILED",
            "error_message": "synthetic test failure",
            "configuration": {},
        }
    )
    assert logger.next_experiment_id() == "EXP_000003"
    records = logger.read_all()
    assert [record["status"] for record in records] == ["SUCCESS", "FAILED"]
    assert all("recorded_at" in record for record in records)


def test_jsonl_is_one_valid_object_per_line(tmp_path):
    trace = JsonlTrace(tmp_path / "trace.jsonl")
    trace.append({"event": 1})
    trace.append({"event": 2})
    lines = trace.path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event"] for line in lines] == [1, 2]

