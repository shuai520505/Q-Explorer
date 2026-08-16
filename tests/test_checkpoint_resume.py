from src.v03 import TaskCheckpoint


def test_checkpoint_roundtrip_preserves_completed_experiments(tmp_path):
    checkpoint = TaskCheckpoint(tmp_path / "checkpoint.json")
    checkpoint.save({"spent": 4, "completed_experiment_ids": ["E1", "E2"]})
    assert checkpoint.load()["spent"] == 4
    assert checkpoint.completed_experiment_ids() == {"E1", "E2"}

