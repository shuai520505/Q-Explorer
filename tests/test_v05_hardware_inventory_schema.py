import pytest

from src.v05_gate0 import HardwareDevice


def test_v05_hardware_inventory_schema_is_serializable_and_validated():
    device = HardwareDevice("D1", "device", num_qubits=4, supports_raw_counts=True)
    assert device.to_dict()["num_qubits"] == 4
    with pytest.raises(ValueError):
        HardwareDevice("", "device")
