"""Tests for the FastAPI REST API.

API エンドポイントのテスト。
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import UploadResponse, _bodies, app

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_configs"
SANCTAR_CFG = SAMPLE_DIR / "Sanctar.cfg"

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_bodies() -> None:  # type: ignore[misc]
    """Clear the in-memory body store before each test.

    各テスト前にボディストアをクリアする。
    """
    _bodies.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_sanctar() -> UploadResponse:
    """Upload Sanctar.cfg and return the parsed response.

    Sanctar.cfg をアップロードしてレスポンスを返す。
    """
    content = SANCTAR_CFG.read_bytes()
    resp = client.post("/upload-config", files={"file": ("Sanctar.cfg", content, "text/plain")})
    assert resp.status_code == 200
    return UploadResponse(**resp.json())


# ---------------------------------------------------------------------------
# 1. GET /bodies
# ---------------------------------------------------------------------------


class TestListBodies:
    """Tests for the GET /bodies endpoint.

    天体一覧エンドポイントのテスト。
    """

    def test_empty_initially(self) -> None:
        resp = client.get("/bodies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_populated_after_upload(self) -> None:
        _upload_sanctar()
        resp = client.get("/bodies")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        names = [b["name"] for b in data]
        assert "Kerbin" in names

    def test_body_summary_fields(self) -> None:
        _upload_sanctar()
        resp = client.get("/bodies")
        body = resp.json()[0]
        assert "name" in body
        assert "display_name" in body
        assert "radius" in body
        assert "gee_asl" in body
        assert "has_atmosphere" in body
        assert "has_ocean" in body


# ---------------------------------------------------------------------------
# 2. POST /upload-config
# ---------------------------------------------------------------------------


class TestUploadConfig:
    """Tests for the POST /upload-config endpoint.

    設定ファイルアップロードのテスト。
    """

    def test_upload_sanctar(self) -> None:
        result = _upload_sanctar()
        assert result.count >= 1
        assert "Kerbin" in result.bodies_added

    def test_upload_empty_file(self) -> None:
        resp = client.post("/upload-config", files={"file": ("empty.cfg", b"", "text/plain")})
        assert resp.status_code == 400

    def test_upload_no_bodies(self) -> None:
        content = b"SomeNode\n{\n    key = value\n}\n"
        resp = client.post("/upload-config", files={"file": ("test.cfg", content, "text/plain")})
        assert resp.status_code == 400

    def test_upload_invalid_encoding(self) -> None:
        resp = client.post(
            "/upload-config",
            files={"file": ("bad.cfg", b"\xff\xfe\x00\x00", "text/plain")},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 3. GET /bodies/{name}
# ---------------------------------------------------------------------------


class TestGetBodyDetail:
    """Tests for the GET /bodies/{name} endpoint.

    天体詳細エンドポイントのテスト。
    """

    def test_not_found(self) -> None:
        resp = client.get("/bodies/NonExistent")
        assert resp.status_code == 404

    def test_sanctar_detail(self) -> None:
        _upload_sanctar()
        resp = client.get("/bodies/Kerbin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Kerbin"
        assert math.isclose(data["radius"], 670_000.0, rel_tol=1e-9)
        assert math.isclose(data["gee_asl"], 1.1, rel_tol=1e-9)
        assert math.isclose(data["mu"], 4.8424e12, rel_tol=1e-3)

    def test_atmosphere_present(self) -> None:
        _upload_sanctar()
        resp = client.get("/bodies/Kerbin")
        data = resp.json()
        atmo = data["atmosphere"]
        assert atmo is not None
        assert math.isclose(atmo["atmosphere_depth"], 72_000.0, rel_tol=1e-9)
        assert atmo["sea_level_density"] is not None
        assert math.isclose(atmo["sea_level_density"], 1.4096, rel_tol=1e-3)

    def test_orbit_present(self) -> None:
        _upload_sanctar()
        resp = client.get("/bodies/Kerbin")
        data = resp.json()
        orbit = data["orbit"]
        assert orbit is not None
        assert math.isclose(orbit["semi_major_axis"], 13116000574.0188, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# 4. POST /calc/launch
# ---------------------------------------------------------------------------


class TestCalcLaunch:
    """Tests for the POST /calc/launch endpoint.

    低軌道投入ΔV計算のテスト。リファレンス値との比較を含む。
    """

    def test_body_not_found(self) -> None:
        resp = client.post("/calc/launch", json={"body_name": "X", "target_altitude": 80000})
        assert resp.status_code == 404

    def test_sanctar_reference(self) -> None:
        """Regression: Sanctar 80km ΔV values."""
        _upload_sanctar()
        resp = client.post("/calc/launch", json={"body_name": "Kerbin", "target_altitude": 80_000})
        assert resp.status_code == 200
        data = resp.json()
        assert math.isclose(data["orbital_velocity"], 2541.1, rel_tol=1e-3)
        assert math.isclose(data["total_rocket"], 3110.0, rel_tol=0.05)
        assert math.isclose(data["total_with_jets"], 1982.0, rel_tol=0.05)

    def test_consistency(self) -> None:
        _upload_sanctar()
        resp = client.post("/calc/launch", json={"body_name": "Kerbin", "target_altitude": 80_000})
        data = resp.json()
        expected_rocket = data["orbital_velocity"] + data["gravity_loss"] + data["drag_loss"]
        assert math.isclose(data["total_rocket"], expected_rocket, rel_tol=1e-9)
        expected_jets = data["total_rocket"] - data["jet_savings"]
        assert math.isclose(data["total_with_jets"], expected_jets, rel_tol=1e-9)

    def test_negative_altitude_rejected(self) -> None:
        _upload_sanctar()
        resp = client.post("/calc/launch", json={"body_name": "Kerbin", "target_altitude": -100})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 5. POST /calc/hohmann
# ---------------------------------------------------------------------------


class TestCalcHohmann:
    """Tests for the POST /calc/hohmann endpoint.

    ホーマン遷移計算のテスト。
    """

    def test_body_not_found(self) -> None:
        resp = client.post(
            "/calc/hohmann",
            json={"body_name": "X", "parking_altitude": 80000, "target_sma": 900000},
        )
        assert resp.status_code == 404

    def test_basic_transfer(self) -> None:
        _upload_sanctar()
        target_sma = 670_000 + 200_000
        resp = client.post(
            "/calc/hohmann",
            json={
                "body_name": "Kerbin",
                "parking_altitude": 80_000,
                "target_sma": target_sma,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["departure_dv"] > 0
        assert data["arrival_dv"] > 0
        assert math.isclose(data["total_dv"], data["departure_dv"] + data["arrival_dv"])
        assert data["transfer_time"] > 0

    def test_target_below_parking_fails(self) -> None:
        _upload_sanctar()
        resp = client.post(
            "/calc/hohmann",
            json={"body_name": "Kerbin", "parking_altitude": 80_000, "target_sma": 700_000},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 6. POST /calc/tsiolkovsky
# ---------------------------------------------------------------------------


class TestCalcTsiolkovsky:
    """Tests for the POST /calc/tsiolkovsky endpoint.

    ツィオルコフスキー方程式のテスト。
    """

    def test_basic(self) -> None:
        resp = client.post(
            "/calc/tsiolkovsky",
            json={"delta_v": 3110, "isp": 340, "wet_mass": 10000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["mass_ratio"] > 1.0
        assert 0 < data["fuel_fraction"] < 1.0
        assert math.isclose(data["dry_mass"] + data["fuel_mass"], 10000, rel_tol=1e-9)

    def test_zero_delta_v(self) -> None:
        resp = client.post(
            "/calc/tsiolkovsky",
            json={"delta_v": 0, "isp": 340, "wet_mass": 10000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert math.isclose(data["mass_ratio"], 1.0)
        assert math.isclose(data["fuel_mass"], 0.0, abs_tol=1e-9)

    def test_negative_isp_rejected(self) -> None:
        resp = client.post(
            "/calc/tsiolkovsky",
            json={"delta_v": 1000, "isp": -1, "wet_mass": 10000},
        )
        assert resp.status_code == 422

    def test_zero_mass_rejected(self) -> None:
        resp = client.post(
            "/calc/tsiolkovsky",
            json={"delta_v": 1000, "isp": 340, "wet_mass": 0},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 7. GET /atmo-profile/{name}
# ---------------------------------------------------------------------------


class TestAtmoProfile:
    """Tests for the GET /atmo-profile/{name} endpoint.

    大気プロファイルエンドポイントのテスト。
    """

    def test_not_found(self) -> None:
        resp = client.get("/atmo-profile/NonExistent")
        assert resp.status_code == 404

    def test_sanctar_profile(self) -> None:
        _upload_sanctar()
        resp = client.get("/atmo-profile/Kerbin?steps=50")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["altitude"]) == 51  # steps + 1
        assert len(data["pressure"]) == 51
        assert len(data["temperature"]) == 51
        assert len(data["density"]) == 51
        # First altitude is 0
        assert data["altitude"][0] == 0.0
        # Pressure decreases with altitude
        assert data["pressure"][0] > data["pressure"][-1]
        # Density at sea level close to reference
        assert math.isclose(data["density"][0], 1.4096, rel_tol=1e-3)

    def test_airless_body_returns_400(self) -> None:
        # Add an airless body manually
        client.post(
            "/bodies/manual",
            json={"name": "Airless", "radius": 200000, "gee_asl": 0.138},
        )
        resp = client.get("/atmo-profile/Airless")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 8. POST /bodies/manual
# ---------------------------------------------------------------------------


class TestManualBody:
    """Tests for the POST /bodies/manual endpoint.

    天体手動追加のテスト。
    """

    def test_add_body(self) -> None:
        resp = client.post(
            "/bodies/manual",
            json={"name": "TestBody", "radius": 100000, "gee_asl": 0.5},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "TestBody"
        assert data["display_name"] == "TestBody"
        assert math.isclose(data["radius"], 100_000.0)
        assert math.isclose(data["gee_asl"], 0.5)
        assert data["atmosphere"] is None
        assert data["orbit"] is None

    def test_add_body_with_display_name(self) -> None:
        resp = client.post(
            "/bodies/manual",
            json={
                "name": "TestBody",
                "radius": 100000,
                "gee_asl": 0.5,
                "display_name": "My Body",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["display_name"] == "My Body"

    def test_added_body_appears_in_list(self) -> None:
        client.post(
            "/bodies/manual",
            json={"name": "Listed", "radius": 50000, "gee_asl": 1.0},
        )
        resp = client.get("/bodies")
        names = [b["name"] for b in resp.json()]
        assert "Listed" in names

    def test_invalid_radius_rejected(self) -> None:
        resp = client.post(
            "/bodies/manual",
            json={"name": "Bad", "radius": -1, "gee_asl": 1.0},
        )
        assert resp.status_code == 422

    def test_mu_auto_derived(self) -> None:
        resp = client.post(
            "/bodies/manual",
            json={"name": "MuTest", "radius": 670000, "gee_asl": 1.1},
        )
        data = resp.json()
        assert math.isclose(data["mu"], 4.8424e12, rel_tol=1e-3)


# ---------------------------------------------------------------------------
# 9. Error cases
# ---------------------------------------------------------------------------


class TestErrorCases:
    """General error case tests.

    一般的なエラーケースのテスト。
    """

    def test_404_body_detail(self) -> None:
        resp = client.get("/bodies/NoSuchBody")
        assert resp.status_code == 404
        assert "detail" in resp.json()

    def test_404_calc_launch(self) -> None:
        resp = client.post(
            "/calc/launch", json={"body_name": "NoSuchBody", "target_altitude": 80000}
        )
        assert resp.status_code == 404

    def test_404_calc_hohmann(self) -> None:
        resp = client.post(
            "/calc/hohmann",
            json={"body_name": "NoSuchBody", "parking_altitude": 80000, "target_sma": 900000},
        )
        assert resp.status_code == 404

    def test_missing_required_field(self) -> None:
        resp = client.post("/calc/launch", json={"body_name": "Kerbin"})
        assert resp.status_code == 422

    def test_lang_query_param(self) -> None:
        resp = client.get("/bodies?lang=en")
        assert resp.status_code == 200

    def test_accept_language_header(self) -> None:
        resp = client.get("/bodies", headers={"Accept-Language": "ja"})
        assert resp.status_code == 200
