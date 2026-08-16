import hashlib
from pathlib import Path

from src.v03c import V03CProtocol


def test_v03c_prompt_matches_formal_v03b_hash():
    protocol = V03CProtocol.load("configs/frozen_v03c.yaml")
    assert hashlib.sha256(Path(protocol.data["prompt_path"]).read_bytes()).hexdigest() == protocol.data["prompt_hash"]
    assert protocol.verify_workspace(".")["prompt"] is True
