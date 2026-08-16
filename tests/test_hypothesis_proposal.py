import pytest

from src.v03 import HypothesisProposal


def test_proposal_requires_scope_falsification_and_alternative():
    proposal = HypothesisProposal("c", {"num_qubits": [4]}, "e", "f", ("alternative",))
    assert proposal.to_dict()["scope"]["num_qubits"] == [4]
    with pytest.raises(ValueError):
        HypothesisProposal("c", {}, "e", "f", ())

