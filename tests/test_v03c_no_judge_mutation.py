from src.v03c import V03CProtocol


def test_v03c_judge_and_vqe_sections_are_unchanged():
    checks = V03CProtocol.load("configs/frozen_v03c.yaml").verify_workspace(".")
    assert checks["scientific_config"] and checks["judge"] and checks["vqe"]
