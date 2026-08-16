from types import SimpleNamespace

from src.v04 import BoundaryEstimator


def _task():
    pool = tuple({"condition_id": f"F{depth}{ent[0].upper()}", "depth": depth, "entanglement": ent} for depth in (1, 2, 3) for ent in ("linear", "ring"))
    return SimpleNamespace(experiment_pool=pool, exploration_set=tuple(row["condition_id"] for row in pool), held_out_set=())


def test_v04_boundary_signature_is_serializable_and_traceable():
    rows = []
    values = {1: (0.1, 0.2), 2: (0.1, 0.3), 3: (0.1, 0.9)}
    for depth, pair in values.items():
        for ent, error in zip(("linear", "ring"), pair):
            rows.append({"condition_id": f"F{depth}{ent[0].upper()}", "experiment_id": f"E{depth}{ent[0]}", "status": "SUCCESS", "energy_error": error})
    signature = BoundaryEstimator(0.05, 0.2).estimate("R", "N1", rows, _task(), True, "H")
    assert signature.candidate_boundary_region == (2, 3)
    assert signature.to_dict()["supporting_experiment_ids"]
