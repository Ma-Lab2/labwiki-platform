"""
Backend API tests for RCF-Web.

Covers sync/async compute, websocket auth, stack validation, and materials upload.
"""

import os
import sys
import json
import uuid

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import app

client = TestClient(app)


def _basic_layers():
    return [
        {"material_name": "Al", "thickness": 30, "thickness_type": "variable", "is_detector": False},
        {"material_name": "HD", "thickness": 105, "thickness_type": "fixed", "is_detector": True, "layer_id": "layer-hd-1"},
    ]


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_materials_list():
    r = client.get("/api/v1/materials/")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    names = [m["name"] for m in data]
    assert "Al" in names or "Aluminum" in names


def test_batch_load():
    r = client.post("/api/v1/materials/batch-load")
    assert r.status_code == 200
    assert r.json()["loaded"] >= 0


def test_stack_validate():
    r = client.post("/api/v1/stack/validate", json=_basic_layers())
    assert r.status_code == 200
    assert r.json()["valid"] is True


def test_stack_validate_no_detector():
    layers = [{"material_name": "Al", "thickness": 30, "is_detector": False, "thickness_type": "variable"}]
    r = client.post("/api/v1/stack/validate", json=layers)
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_stack_validate_negative_thickness_rejected():
    layers = [{"material_name": "Al", "thickness": -1, "is_detector": False, "thickness_type": "variable"}]
    r = client.post("/api/v1/stack/validate", json=layers)
    # Pydantic schema should reject before custom validation route logic.
    assert r.status_code == 422


def test_energy_scan_sync():
    payload = {
        "layers": _basic_layers(),
        "energy_min": 0.5,
        "energy_max": 20.0,
        "energy_step": 0.5,
        "incidence_angle": 0.0,
        "ion_key": "proton",
    }
    r = client.post("/api/v1/compute/energy-scan", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["rcf_results"]) == 1
    assert data["rcf_results"][0]["name"] == "HD"
    assert data["rcf_results"][0]["cutoff_energy"] is not None
    assert data["rcf_results"][0]["layer_id"] == "layer-hd-1"
    assert len(data["energy_range"]) > 0


def test_energy_scan_reject_invalid_energy_range():
    payload = {
        "layers": _basic_layers(),
        "energy_min": 20.0,
        "energy_max": 1.0,
        "energy_step": 0.5,
        "incidence_angle": 0.0,
        "ion_key": "proton",
    }
    r = client.post("/api/v1/compute/energy-scan", json=payload)
    assert r.status_code == 422


def test_energy_scan_oblique():
    """Oblique incidence should increase cutoff energy."""
    base = {
        "layers": _basic_layers(),
        "energy_min": 0.5,
        "energy_max": 30.0,
        "energy_step": 0.5,
        "ion_key": "proton",
    }

    r0 = client.post("/api/v1/compute/energy-scan", json={**base, "incidence_angle": 0.0})
    r15 = client.post("/api/v1/compute/energy-scan", json={**base, "incidence_angle": 15.0})

    e0 = r0.json()["rcf_results"][0]["cutoff_energy"]
    e15 = r15.json()["rcf_results"][0]["cutoff_energy"]
    assert e15 >= e0


def test_energy_scan_async_and_websocket_flow():
    payload = {
        "layers": _basic_layers(),
        "energy_min": 0.5,
        "energy_max": 10.0,
        "energy_step": 1.0,
    }
    r = client.post("/api/v1/compute/energy-scan/async", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "task_id" in data
    assert "ws_token" in data

    ws_path = f"/api/v1/ws/compute/{data['task_id']}?token={data['ws_token']}"
    with client.websocket_connect(ws_path) as websocket:
        got_terminal = False
        for _ in range(100):
            msg = websocket.receive_json()
            assert msg["type"] in {"progress", "result", "error"}
            if msg["type"] in {"result", "error"}:
                got_terminal = True
                break
        assert got_terminal


def test_websocket_reject_invalid_token():
    payload = {
        "layers": _basic_layers(),
        "energy_min": 0.5,
        "energy_max": 5.0,
        "energy_step": 1.0,
    }
    r = client.post("/api/v1/compute/energy-scan/async", json=payload)
    assert r.status_code == 200
    task_id = r.json()["task_id"]

    with client.websocket_connect(f"/api/v1/ws/compute/{task_id}?token=wrong-token") as websocket:
        msg = websocket.receive_json()
        assert msg["type"] == "error"


def test_linear_design_sync():
    payload = {
        "detectors": [
            {"material_name": "HD", "thickness": 105, "thickness_type": "fixed", "is_detector": True, "layer_id": "d1"},
            {"material_name": "EBT", "thickness": 280, "thickness_type": "fixed", "is_detector": True, "layer_id": "d2"},
        ],
        "al_thick_1": 30,
        "energy_interval": 2.0,
        "al_thick_min": 0.0,
        "al_thick_max": 200.0,
        "al_interval": 5.0,
        "incidence_angle": 0.0,
    }
    r = client.post("/api/v1/compute/linear-design", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["energy_sequence"]) == 2
    assert len(data["al_thickness_sequence"]) == 2
    assert len(data["full_stack"]) == 4


def test_stack_import_export_roundtrip():
    raw = [
        {"material_name": "Al", "thickness": "30", "thickness_type": "variable", "rcf": None},
        {"material_name": "HD", "thickness": "105", "thickness_type": "fixed", "rcf": {"x": 1}},
    ]
    files = {"file": ("stack.json", json.dumps(raw), "application/json")}
    imported = client.post("/api/v1/stack/import-json", files=files)
    assert imported.status_code == 200
    layers = imported.json()["layers"]
    assert len(layers) == 2
    assert layers[1]["is_detector"] is True

    exported = client.post("/api/v1/stack/export-json", json=layers)
    assert exported.status_code == 200
    assert len(exported.json()) == 2


def test_upload_material_with_replace():
    csv_text = """Energy,Col1,Col2,Col3,Stopping
0.100,0,0,0,100.0
1.000,0,0,0,10.0
10.000,0,0,0,1.0
"""
    material_name = f"UploadTestMaterial_{uuid.uuid4().hex[:8]}"
    files = {"file": ("my_upload.csv", csv_text, "text/csv")}
    data = {"name": material_name, "density": "1.23", "replace": "false"}

    first = client.post("/api/v1/materials/upload-pstar", data=data, files=files)
    assert first.status_code == 200
    assert first.json()["name"] == material_name

    second = client.post("/api/v1/materials/upload-pstar", data=data, files=files)
    assert second.status_code == 400

    replace_data = {"name": material_name, "density": "1.24", "replace": "true"}
    third = client.post("/api/v1/materials/upload-pstar", data=replace_data, files=files)
    assert third.status_code == 200
    assert abs(third.json()["density"] - 1.24) < 1e-6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
