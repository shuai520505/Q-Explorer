from src.v03c import V03CProtocol


def test_v03c_model_and_thinking_mode_are_frozen():
    protocol = V03CProtocol.load("configs/frozen_v03c.yaml")
    assert protocol.data["model"] == "deepseek-v4-flash"
    assert protocol.data["thinking_mode"] is False
    assert protocol.verify_workspace(".")["model"] is True
