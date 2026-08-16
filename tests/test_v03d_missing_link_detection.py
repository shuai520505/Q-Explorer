from src.v03d import EvidenceGraph


def test_v03d_missing_link_is_explicit_and_never_inferred():
    graph = EvidenceGraph({"revisions": [{"revision_id": "REV", "triggering_evidence_ids": ["NOPE"]}]})
    result = graph.get_trigger_path("REV")
    assert result == {"status": "MISSING_LINK", "kind": "evidence", "identifier": "NOPE", "reason": "not_found"}


def test_v03d_historical_revision_without_id_is_not_given_a_fake_id():
    graph = EvidenceGraph({"revisions": [{"triggering_evidence_ids": []}]})
    assert graph.get_trigger_path(graph.records["revisions"][0])["kind"] == "revision_id"
