from src.research import revise_hypothesis


def test_revision_preserves_parent_and_lineage():
    parent = {"hypothesis_id": "H001", "claim": "ring always helps", "status": "NARROWED"}
    child, revision = revise_hypothesis(parent, "ring may help only in a narrowed scope", "counterexample", ["E1"], "universal -> conditional", {"H001"})
    assert parent["claim"] == "ring always helps"
    assert child["hypothesis_id"] == "H001.R1"
    assert child["parent_hypothesis_id"] == "H001"
    assert revision.triggering_evidence_ids == ("E1",)

