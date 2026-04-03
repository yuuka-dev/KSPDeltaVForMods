"""Tests for the FastAPI REST API.

API エンドポイントのテスト。
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")

from fastapi.testclient import TestClient  # noqa: E402

import api as _api_module  # noqa: E402
from api import UploadResponse, _bodies, app  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_configs"
SANCTAR_CFG = SAMPLE_DIR / "Sanctar.cfg"

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_state() -> None:  # type: ignore[misc]
    """Clear the in-memory body store and system before each test.

    各テスト前にボディストアとシステムをクリアする。
    """
    _bodies.clear()
    _api_module._system = None  # type: ignore[assignment]


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


class TestHealth:
    """Tests for the GET /health endpoint.

    ヘルスチェックエンドポイントのテスト。
    """

    def test_health_endpoint(self) -> None:
        """Verify /health returns status ok."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


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
        assert math.isclose(data["total_rocket"], 3891.0, rel_tol=0.05)
        assert math.isclose(data["total_with_jets"], 2899.0, rel_tol=0.05)

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

    def test_inward_transfer_succeeds(self) -> None:
        _upload_sanctar()
        resp = client.post(
            "/calc/hohmann",
            json={"body_name": "Kerbin", "parking_altitude": 80_000, "target_sma": 700_000},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["departure_dv"] > 0
        assert data["arrival_dv"] > 0
        assert data["inward"] is True

    def test_identical_orbits_fails(self) -> None:
        _upload_sanctar()
        resp = client.post(
            "/calc/hohmann",
            json={"body_name": "Kerbin", "parking_altitude": 80_000, "target_sma": 750_000},
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


# ---------------------------------------------------------------------------
# 10. POST /scan
# ---------------------------------------------------------------------------


class TestScanEndpoint:
    """Tests for the POST /scan endpoint.

    スキャンエンドポイントのテスト。
    """

    def test_scan_nonexistent_path(self) -> None:
        """Returns 404 when the path does not exist."""
        resp = client.post(
            "/scan",
            json={"gamedata_path": "/nonexistent/path/that/does/not/exist"},
        )
        assert resp.status_code == 404

    def test_scan_file_instead_of_dir(self, tmp_path: Path) -> None:
        """Returns 404 when the path is a file, not a directory."""
        f = tmp_path / "not_a_dir.cfg"
        f.write_text("nothing")
        resp = client.post("/scan", json={"gamedata_path": str(f)})
        assert resp.status_code == 404

    def test_scan_empty_dir(self, tmp_path: Path) -> None:
        """Returns 404 when no cfg files with bodies are found."""
        resp = client.post("/scan", json={"gamedata_path": str(tmp_path)})
        assert resp.status_code == 404

    def test_scan_populates_bodies(self) -> None:
        """Scanning sample_configs/.. populates _bodies from Sanctar.cfg."""
        resp = client.post(
            "/scan",
            json={"gamedata_path": str(SAMPLE_DIR)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert "Kerbin" in data["bodies_added"]
        # _bodies should also be populated for backward compatibility.
        assert "Kerbin" in _bodies


# ---------------------------------------------------------------------------
# 11. GET /system, /system/home, /system/destinations
# ---------------------------------------------------------------------------


class TestSystemEndpoints:
    """Tests for the system endpoints.

    システムエンドポイントのテスト。
    """

    def test_system_no_data(self) -> None:
        """Returns 404 when no system has been loaded."""
        resp = client.get("/system")
        assert resp.status_code == 404

    def test_system_home_no_data(self) -> None:
        """Returns 404 for /system/home when no system loaded."""
        resp = client.get("/system/home")
        assert resp.status_code == 404

    def test_system_destinations_no_data(self) -> None:
        """Returns 404 for /system/destinations when no system loaded."""
        resp = client.get("/system/destinations")
        assert resp.status_code == 404

    def test_system_after_scan(self) -> None:
        """Returns system data after a successful scan."""
        client.post("/scan", json={"gamedata_path": str(SAMPLE_DIR)})
        resp = client.get("/system")
        assert resp.status_code == 200
        data = resp.json()
        assert "root" in data
        assert "home_world" in data
        assert data["body_count"] >= 1
        assert isinstance(data["tree"], list)

    def test_system_home_after_scan(self) -> None:
        """Returns home world detail after a successful scan."""
        client.post("/scan", json={"gamedata_path": str(SAMPLE_DIR)})
        resp = client.get("/system/home")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Kerbin"


# ---------------------------------------------------------------------------
# 12. POST /calc/route
# ---------------------------------------------------------------------------


class TestRouteEndpoint:
    """Tests for the POST /calc/route endpoint.

    ルート計算エンドポイントのテスト。
    """

    def test_calc_route_no_system(self) -> None:
        """Returns 404 when no system is loaded."""
        resp = client.post("/calc/route", json={})
        assert resp.status_code == 404

    def test_calc_route_unknown_destination(self) -> None:
        """Returns 404 for an unknown destination body."""
        client.post("/scan", json={"gamedata_path": str(SAMPLE_DIR)})
        resp = client.post("/calc/route", json={"destination": "NonExistentPlanet"})
        assert resp.status_code == 404

    def test_calc_route_moon_without_destination_unknown_moon(self) -> None:
        """Returns 404 when moon is unknown (destination=None is now allowed)."""
        client.post("/scan", json={"gamedata_path": str(SAMPLE_DIR)})
        resp = client.post("/calc/route", json={"moon": "Mun"})
        assert resp.status_code == 404

    def test_calc_route_escape_only(self) -> None:
        """Returns 422 when home world has no parent (single-body sample config)."""
        # Sanctar.cfg declares Kerbin referencing 'Sun', but Sun is not in the
        # sample config.  build_tree makes Kerbin the root with no parent, so
        # compute_route raises ValueError → 422.
        client.post("/scan", json={"gamedata_path": str(SAMPLE_DIR)})
        resp = client.post("/calc/route", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 13. GET /bodies/{name}/moons
# ---------------------------------------------------------------------------


class TestMoonsEndpoint:
    """Tests for the GET /bodies/{name}/moons endpoint.

    衛星一覧エンドポイントのテスト。
    """

    def test_moons_no_system(self) -> None:
        """Returns 404 when no system is loaded."""
        resp = client.get("/bodies/Kerbin/moons")
        assert resp.status_code == 404

    def test_moons_unknown_body(self) -> None:
        """Returns 404 for an unknown body name."""
        client.post("/scan", json={"gamedata_path": str(SAMPLE_DIR)})
        resp = client.get("/bodies/NonExistentBody/moons")
        assert resp.status_code == 404

    def test_moons_after_scan(self) -> None:
        """Returns a list (possibly empty) of moons for Kerbin."""
        client.post("/scan", json={"gamedata_path": str(SAMPLE_DIR)})
        resp = client.get("/bodies/Kerbin/moons")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
