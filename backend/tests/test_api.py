"""API-level tests for scan and the cost gate (no fal.ai calls)."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _png(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 90, 200)).save(buf, format="PNG")
    return buf.getvalue()


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_config_never_exposes_key():
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert "fal_key" not in body
    assert "FAL_KEY" not in str(body)
    assert body["default_scale_factor"] == 2


def test_scan_computes_cost_and_gate():
    files = [
        ("images", ("ring.png", _png(2000, 2000), "image/png")),
        ("images", ("pendant.png", _png(1000, 1000), "image/png")),
    ]
    r = client.post("/api/scan", files=files, data={"scale_factor": "2"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_images"] == 2
    # 2000x2000 @2x -> 16 MP -> $0.256 ; 1000x1000 @2x -> 4 MP -> $0.064
    costs = sorted(i["estimated_cost_usd"] for i in body["images"])
    assert abs(costs[0] - 0.064) < 1e-6
    assert abs(costs[1] - 0.256) < 1e-6
    assert abs(body["total_cost_usd"] - 0.32) < 1e-6
    scan_id = body["scan_id"]

    # Cost gate: unconfirmed job is rejected.
    r2 = client.post("/api/jobs", json={"scan_id": scan_id, "confirmed": False})
    assert r2.status_code == 400

    # Unknown scan id.
    r3 = client.post("/api/jobs", json={"scan_id": "scan_missing", "confirmed": True})
    assert r3.status_code == 404


def test_scan_rejects_bad_image_but_keeps_good():
    files = [
        ("images", ("good.png", _png(100, 100), "image/png")),
        ("images", ("bad.png", b"garbage", "image/png")),
        ("images", ("nope.gif", _png(10, 10), "image/gif")),
    ]
    r = client.post("/api/scan", files=files, data={"scale_factor": "2"})
    assert r.status_code == 200
    body = r.json()
    assert body["total_images"] == 1
    assert len(body["errors"]) == 2
