from src.baselines import FixedExplorer
from src.research import Observation, ResearchState


def test_fixed_explorer_uses_preregistered_condition():
    state = ResearchState(1, ({"hypothesis_id": "H001", "claim": "c", "status": "PENDING"},), {"H001": "PENDING"}, {"H001": ()}, {"H001": ()}, (), (), (
        {"hamiltonian_id": "HAM_A", "depth": 1, "entanglement": "ring", "set": "exploration", "seed_group": [1, 2]},
        {"hamiltonian_id": "HAM_B", "depth": 2, "entanglement": "linear", "set": "exploration", "seed_group": [1, 2]},
    ), 10, (), {}, (), (), (), ())
    action = FixedExplorer(2, "linear").select_action(Observation.from_state(state), "ACT_000001")
    assert action.experiment.depth == 2
    assert action.experiment.entanglement == "linear"

