"""Tests for the Kopernicus ConfigNode parser.

Kopernicus ConfigNode パーサーの包括的テスト。
低レベルの ConfigNode パース、カーブキー解析、天体抽出、
エッジケース、回帰テストを網羅する。
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from kopdeltav.models import CurveKey
from kopdeltav.parser import ConfigNode, parse_bodies, parse_config_text

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_configs"
SANCTAR_CFG = SAMPLE_DIR / "Sanctar.cfg"


# ---------------------------------------------------------------------------
# 1. ConfigNode low-level parser tests
# ---------------------------------------------------------------------------


class TestParseConfigText:
    """Low-level ConfigNode parsing tests.

    ConfigNode テキストパーサーの基本動作テスト。
    """

    def test_empty_input_returns_empty_list(self) -> None:
        assert parse_config_text("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert parse_config_text("   \n\t\n  ") == []

    def test_simple_key_value_pairs(self) -> None:
        source = "Node\n{\n    name = Kerbin\n    radius = 600000\n}"
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        assert nodes[0].name == "Node"
        values = dict(nodes[0].values)
        assert values["name"] == "Kerbin"
        assert values["radius"] == "600000"

    def test_nested_nodes(self) -> None:
        source = "Outer\n{\n    key = val\n    Inner\n    {\n        key = val2\n    }\n}\n"
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        outer = nodes[0]
        assert outer.name == "Outer"
        assert dict(outer.values)["key"] == "val"
        assert len(outer.children) == 1
        inner = outer.children[0]
        assert inner.name == "Inner"
        assert dict(inner.values)["key"] == "val2"

    def test_multiple_top_level_nodes(self) -> None:
        source = "A\n{\n    x = 1\n}\nB\n{\n    y = 2\n}\n"
        nodes = parse_config_text(source)
        assert len(nodes) == 2
        assert nodes[0].name == "A"
        assert nodes[1].name == "B"

    def test_comment_removal_full_line(self) -> None:
        source = "// This is a comment\nNode\n{\n    key = val\n}\n"
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        assert dict(nodes[0].values)["key"] == "val"

    def test_comment_removal_inline(self) -> None:
        source = "Node\n{\n    key = val // inline comment\n}\n"
        nodes = parse_config_text(source)
        values = dict(nodes[0].values)
        assert values["key"] == "val"

    def test_modifier_stripping_at(self) -> None:
        source = "@Node\n{\n    key = val\n}\n"
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        assert nodes[0].name == "Node"

    def test_modifier_stripping_exclamation(self) -> None:
        source = "!Node\n{\n    key = val\n}\n"
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        assert nodes[0].name == "Node"

    def test_modifier_stripping_plus(self) -> None:
        source = "+Node\n{\n    key = val\n}\n"
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        assert nodes[0].name == "Node"

    def test_modifier_stripping_minus(self) -> None:
        source = "-Node\n{\n    key = val\n}\n"
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        assert nodes[0].name == "Node"

    def test_modifier_stripping_percent(self) -> None:
        source = "%Node\n{\n    key = val\n}\n"
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        assert nodes[0].name == "Node"

    def test_delete_directive_skipped(self) -> None:
        source = "!Body[Kerbin]{}\nNode\n{\n    key = val\n}\n"
        nodes = parse_config_text(source)
        # The delete directive should be skipped entirely
        node_names = [n.name for n in nodes]
        assert "Body" not in node_names or all(
            n.values or n.children for n in nodes if n.name == "Body"
        )
        # At minimum, the real Node should be present
        assert any(n.name == "Node" for n in nodes)

    def test_mixed_tab_space_indentation(self) -> None:
        source = "Node\n{\n\t  key = val\n\t  \tkey2 = val2\n}\n"
        nodes = parse_config_text(source)
        values = dict(nodes[0].values)
        assert values["key"] == "val"
        assert values["key2"] == "val2"

    def test_empty_lines_between_entries(self) -> None:
        source = "Node\n{\n\n    key1 = val1\n\n    key2 = val2\n\n}\n"
        nodes = parse_config_text(source)
        values = dict(nodes[0].values)
        assert values["key1"] == "val1"
        assert values["key2"] == "val2"

    def test_values_with_spaces(self) -> None:
        source = "Node\n{\n    name = North Pole\n}\n"
        nodes = parse_config_text(source)
        values = dict(nodes[0].values)
        assert values["name"] == "North Pole"

    def test_values_with_scientific_notation(self) -> None:
        source = "Node\n{\n    radius = 1.10444E+02\n}\n"
        nodes = parse_config_text(source)
        values = dict(nodes[0].values)
        assert values["radius"] == "1.10444E+02"

    def test_malformed_unclosed_brace_does_not_crash(self) -> None:
        source = "Node\n{\n    key = val\n"
        # Should not raise an exception
        result = parse_config_text(source)
        assert isinstance(result, list)

    def test_malformed_missing_equals_does_not_crash(self) -> None:
        source = "Node\n{\n    this has no equals\n    key = val\n}\n"
        # Should not crash, may skip the malformed line
        result = parse_config_text(source)
        assert isinstance(result, list)

    def test_deeply_nested_structure(self) -> None:
        source = (
            "A\n{\n"
            "    B\n    {\n"
            "        C\n        {\n"
            "            key = deep\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        nodes = parse_config_text(source)
        assert len(nodes) == 1
        assert nodes[0].name == "A"
        b_node = nodes[0].children[0]
        assert b_node.name == "B"
        c_node = b_node.children[0]
        assert c_node.name == "C"
        assert dict(c_node.values)["key"] == "deep"

    def test_confignode_dataclass_fields(self) -> None:
        source = "Node\n{\n    k = v\n    Child\n    {\n    }\n}\n"
        nodes = parse_config_text(source)
        node = nodes[0]
        assert isinstance(node, ConfigNode)
        assert isinstance(node.name, str)
        assert isinstance(node.values, list)
        assert isinstance(node.children, list)


# ---------------------------------------------------------------------------
# 2. Curve key parsing tests
# ---------------------------------------------------------------------------


class TestCurveKeyParsing:
    """Tests for CurveKey extraction from ConfigNode key values.

    カーブキー文字列から CurveKey への変換テスト。
    """

    def test_full_format_four_values(self) -> None:
        """Full format: position value inTangent outTangent."""
        source = (
            "temperatureCurve\n"
            "{\n"
            "    key = 0 273 0.00000E+00 -5.35664E-03\n"
            "}\n"
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "    Atmosphere\n    {\n"
            "        enabled = True\n"
            "        altitude = 70000\n"
            "        adiabaticIndex = 1.4\n"
            "        atmosphereMolarMass = 0.029\n"
            "        temperatureSeaLevel = 273\n"
            "        staticPressureASL = 101.325\n"
            "        temperatureCurve\n        {\n"
            "            key = 0 273 0.00000E+00 -5.35664E-03\n"
            "        }\n"
            "        pressureCurve\n        {\n"
            "            key = 0 101.325 0 0\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) >= 1
        body = bodies[0]
        assert body.atmosphere is not None
        curve = body.atmosphere.temperature_curve
        assert len(curve) == 1
        key = curve[0]
        assert isinstance(key, CurveKey)
        assert math.isclose(key.position, 0.0, abs_tol=1e-9)
        assert math.isclose(key.value, 273.0, abs_tol=1e-9)
        assert math.isclose(key.in_tangent, 0.0, abs_tol=1e-9)
        assert math.isclose(key.out_tangent, -5.35664e-03, rel_tol=1e-5)

    def test_three_values_out_tangent_copies_in(self) -> None:
        """When outTangent is omitted, it copies inTangent."""
        source = (
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "    Atmosphere\n    {\n"
            "        enabled = True\n"
            "        altitude = 70000\n"
            "        adiabaticIndex = 1.4\n"
            "        atmosphereMolarMass = 0.029\n"
            "        temperatureSeaLevel = 273\n"
            "        staticPressureASL = 101.325\n"
            "        temperatureCurve\n        {\n"
            "            key = 0 273 1.5\n"
            "        }\n"
            "        pressureCurve\n        {\n"
            "            key = 0 101.325 0 0\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        body = bodies[0]
        assert body.atmosphere is not None
        key = body.atmosphere.temperature_curve[0]
        assert math.isclose(key.in_tangent, 1.5, abs_tol=1e-9)
        assert math.isclose(key.out_tangent, 1.5, abs_tol=1e-9)

    def test_two_values_tangents_default_zero(self) -> None:
        """When both tangents are omitted, they default to 0."""
        source = (
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "    Atmosphere\n    {\n"
            "        enabled = True\n"
            "        altitude = 70000\n"
            "        adiabaticIndex = 1.4\n"
            "        atmosphereMolarMass = 0.029\n"
            "        temperatureSeaLevel = 273\n"
            "        staticPressureASL = 101.325\n"
            "        temperatureCurve\n        {\n"
            "            key = 0 273\n"
            "        }\n"
            "        pressureCurve\n        {\n"
            "            key = 0 101.325 0 0\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        body = bodies[0]
        assert body.atmosphere is not None
        key = body.atmosphere.temperature_curve[0]
        assert math.isclose(key.in_tangent, 0.0, abs_tol=1e-9)
        assert math.isclose(key.out_tangent, 0.0, abs_tol=1e-9)

    def test_scientific_notation_in_all_positions(self) -> None:
        """Scientific notation parses correctly in all four fields."""
        source = (
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "    Atmosphere\n    {\n"
            "        enabled = True\n"
            "        altitude = 70000\n"
            "        adiabaticIndex = 1.4\n"
            "        atmosphereMolarMass = 0.029\n"
            "        temperatureSeaLevel = 273\n"
            "        staticPressureASL = 101.325\n"
            "        temperatureCurve\n        {\n"
            "            key = 1.0E+04 2.73E+02 -1.5E-03 -2.0E-03\n"
            "        }\n"
            "        pressureCurve\n        {\n"
            "            key = 0 101.325 0 0\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        body = bodies[0]
        assert body.atmosphere is not None
        key = body.atmosphere.temperature_curve[0]
        assert math.isclose(key.position, 1.0e4, rel_tol=1e-9)
        assert math.isclose(key.value, 273.0, rel_tol=1e-9)
        assert math.isclose(key.in_tangent, -1.5e-3, rel_tol=1e-5)
        assert math.isclose(key.out_tangent, -2.0e-3, rel_tol=1e-5)

    def test_negative_values_in_curve_keys(self) -> None:
        """Negative numbers parse correctly."""
        source = (
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "    Atmosphere\n    {\n"
            "        enabled = True\n"
            "        altitude = 70000\n"
            "        adiabaticIndex = 1.4\n"
            "        atmosphereMolarMass = 0.029\n"
            "        temperatureSeaLevel = 273\n"
            "        staticPressureASL = 101.325\n"
            "        temperatureCurve\n        {\n"
            "            key = -100 -50.5 -0.01 -0.02\n"
            "        }\n"
            "        pressureCurve\n        {\n"
            "            key = 0 101.325 0 0\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        body = bodies[0]
        assert body.atmosphere is not None
        key = body.atmosphere.temperature_curve[0]
        assert math.isclose(key.position, -100.0, abs_tol=1e-9)
        assert math.isclose(key.value, -50.5, abs_tol=1e-9)
        assert math.isclose(key.in_tangent, -0.01, abs_tol=1e-9)
        assert math.isclose(key.out_tangent, -0.02, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# 3. Body extraction tests (Sanctar.cfg)
# ---------------------------------------------------------------------------


class TestParseBodies:
    """Integration tests against the real Sanctar.cfg sample config.

    実際の Sanctar.cfg を使った天体抽出の統合テスト。
    """

    @pytest.fixture()
    def sanctar_bodies(self) -> list:
        """Load and parse the Sanctar sample config.

        Sanctar.cfg を読み込みパースする。
        """
        source = SANCTAR_CFG.read_text(encoding="utf-8")
        return parse_bodies(source)

    @pytest.fixture()
    def sanctar(self, sanctar_bodies: list) -> object:
        """Extract the single body from Sanctar config.

        Sanctar 天体オブジェクトを取得する。
        """
        assert len(sanctar_bodies) >= 1
        return sanctar_bodies[0]

    def test_body_name(self, sanctar: object) -> None:
        assert sanctar.name == "Kerbin"  # type: ignore[attr-defined]

    def test_display_name_fallback(self, sanctar: object) -> None:
        """#LOC_ prefixed displayName should fall back to name."""
        # displayName = #LOC_CH_Sanctar_displayName -> falls back to "Kerbin"
        assert sanctar.display_name == "Kerbin"  # type: ignore[attr-defined]

    def test_radius(self, sanctar: object) -> None:
        assert math.isclose(sanctar.radius, 670_000.0, rel_tol=1e-9)  # type: ignore[attr-defined]

    def test_gee_asl(self, sanctar: object) -> None:
        assert math.isclose(sanctar.gee_asl, 1.1, rel_tol=1e-9)  # type: ignore[attr-defined]

    def test_mu_auto_derived(self, sanctar: object) -> None:
        """mu should be auto-derived: geeASL * G0 * radius^2 ~ 4.8424e12."""
        assert math.isclose(sanctar.mu, 4.8424e12, rel_tol=1e-3)  # type: ignore[attr-defined]

    def test_rotational_period(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.rotational_period,  # type: ignore[attr-defined]
            90291.8154599763,
            rel_tol=1e-9,
        )

    def test_has_ocean(self, sanctar: object) -> None:
        assert sanctar.has_ocean is True  # type: ignore[attr-defined]

    def test_atmosphere_is_not_none(self, sanctar: object) -> None:
        assert sanctar.atmosphere is not None  # type: ignore[attr-defined]

    def test_atmosphere_depth(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.atmosphere.atmosphere_depth,  # type: ignore[attr-defined]
            72_000.0,
            rel_tol=1e-9,
        )

    def test_atmosphere_adiabatic_index(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.atmosphere.adiabatic_index,  # type: ignore[attr-defined]
            1.40,
            rel_tol=1e-9,
        )

    def test_atmosphere_molar_mass(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.atmosphere.molar_mass,  # type: ignore[attr-defined]
            0.02897,
            rel_tol=1e-9,
        )

    def test_atmosphere_temperature_at_sea_level(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.atmosphere.temperature_at_sea_level,  # type: ignore[attr-defined]
            281.0,
            rel_tol=1e-9,
        )

    def test_atmosphere_pressure_at_sea_level(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.atmosphere.pressure_at_sea_level,  # type: ignore[attr-defined]
            110.444,
            rel_tol=1e-3,
        )

    def test_pressure_curve_count(self, sanctar: object) -> None:
        """pressureCurve should have exactly 26 keys."""
        assert len(sanctar.atmosphere.pressure_curve) == 26  # type: ignore[attr-defined]

    def test_temperature_curve_count(self, sanctar: object) -> None:
        """temperatureCurve should have exactly 26 keys."""
        assert len(sanctar.atmosphere.temperature_curve) == 26  # type: ignore[attr-defined]

    def test_first_pressure_curve_key(self, sanctar: object) -> None:
        key = sanctar.atmosphere.pressure_curve[0]  # type: ignore[attr-defined]
        assert math.isclose(key.position, 0.0, abs_tol=1e-9)
        assert math.isclose(key.value, 110.444, rel_tol=1e-3)

    def test_last_pressure_curve_key(self, sanctar: object) -> None:
        key = sanctar.atmosphere.pressure_curve[-1]  # type: ignore[attr-defined]
        assert math.isclose(key.position, 72_000.0, rel_tol=1e-9)
        assert math.isclose(key.value, 0.0, abs_tol=1e-9)

    def test_orbit_is_not_none(self, sanctar: object) -> None:
        assert sanctar.orbit is not None  # type: ignore[attr-defined]

    def test_orbit_semi_major_axis(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.orbit.semi_major_axis,  # type: ignore[attr-defined]
            13116000574.0188,
            rel_tol=1e-6,
        )

    def test_orbit_eccentricity(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.orbit.eccentricity,  # type: ignore[attr-defined]
            0.0254528329387812,
            rel_tol=1e-6,
        )

    def test_orbit_inclination(self, sanctar: object) -> None:
        assert math.isclose(
            sanctar.orbit.inclination,  # type: ignore[attr-defined]
            1.38,
            rel_tol=1e-9,
        )


# ---------------------------------------------------------------------------
# 4. Edge case tests
# ---------------------------------------------------------------------------


class TestParserEdgeCases:
    """Edge cases for the parser that should be handled gracefully.

    パーサーが適切に処理すべきエッジケースのテスト。
    """

    def test_no_body_nodes_returns_empty_list(self) -> None:
        source = "SomeOtherNode\n{\n    key = val\n}\n"
        bodies = parse_bodies(source)
        assert bodies == []

    def test_atmosphere_disabled_is_none(self) -> None:
        """Atmosphere with enabled=False should result in atmosphere=None."""
        source = (
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "    Atmosphere\n    {\n"
            "        enabled = False\n"
            "        altitude = 70000\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) == 1
        assert bodies[0].atmosphere is None

    def test_no_orbit_node_orbit_is_none(self) -> None:
        source = (
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) == 1
        assert bodies[0].orbit is None

    def test_no_ocean_node_has_ocean_false(self) -> None:
        source = (
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) == 1
        assert bodies[0].has_ocean is False

    def test_minimal_body(self) -> None:
        """Body with only name, radius, geeASL should still parse."""
        source = (
            "Body\n{\n"
            "    name = Minimal\n"
            "    Properties\n    {\n"
            "        radius = 50000\n"
            "        geeASL = 0.5\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) == 1
        body = bodies[0]
        assert body.name == "Minimal"
        assert math.isclose(body.radius, 50_000.0, rel_tol=1e-9)
        assert math.isclose(body.gee_asl, 0.5, rel_tol=1e-9)
        assert body.atmosphere is None
        assert body.orbit is None
        assert body.has_ocean is False

    def test_multiple_body_blocks(self) -> None:
        source = (
            "Body\n{\n"
            "    name = Alpha\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "}\n"
            "Body\n{\n"
            "    name = Beta\n"
            "    Properties\n    {\n"
            "        radius = 200000\n"
            "        geeASL = 0.8\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) == 2
        names = {b.name for b in bodies}
        assert names == {"Alpha", "Beta"}

    def test_deeply_nested_irrelevant_nodes_ignored(self) -> None:
        """PQS, ScaledVersion etc. should be ignored without errors."""
        source = (
            "Body\n{\n"
            "    name = Test\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "    PQS\n    {\n"
            "        Mods\n        {\n"
            "            VertexColorMap\n            {\n"
            "                map = some/path.dds\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "    ScaledVersion\n    {\n"
            "        type = Atmospheric\n"
            "        Material\n        {\n"
            "            texture = some/path.dds\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) == 1
        assert bodies[0].name == "Test"

    def test_body_inside_kopernicus_wrapper(self) -> None:
        """Body nested inside a @Kopernicus wrapper should still be found."""
        source = (
            "@Kopernicus:AFTER[Kopernicus]\n"
            "{\n"
            "    Body\n"
            "    {\n"
            "        name = Wrapped\n"
            "        Properties\n"
            "        {\n"
            "            radius = 300000\n"
            "            geeASL = 0.9\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) >= 1
        assert any(b.name == "Wrapped" for b in bodies)

    def test_delete_directive_followed_by_body(self) -> None:
        """!Body[Name]{} delete directive should not interfere with real bodies."""
        source = (
            "!Body[OldBody]{}\n"
            "Body\n{\n"
            "    name = NewBody\n"
            "    Properties\n    {\n"
            "        radius = 100000\n"
            "        geeASL = 1.0\n"
            "    }\n"
            "}\n"
        )
        bodies = parse_bodies(source)
        assert len(bodies) >= 1
        assert any(b.name == "NewBody" for b in bodies)


# ---------------------------------------------------------------------------
# 5. Regression tests (reference values from CLAUDE.md)
# ---------------------------------------------------------------------------


class TestParserRegression:
    """Regression tests ensuring Sanctar reference values from CLAUDE.md hold.

    CLAUDE.md のリファレンス値との整合性テスト。
    """

    @pytest.fixture()
    def sanctar(self) -> object:
        """Load Sanctar body from sample config.

        Sanctar 天体をサンプル config から読み込む。
        """
        source = SANCTAR_CFG.read_text(encoding="utf-8")
        bodies = parse_bodies(source)
        assert len(bodies) >= 1
        return bodies[0]

    def test_radius_670000(self, sanctar: object) -> None:
        """Reference: radius = 670,000 m."""
        assert math.isclose(sanctar.radius, 670_000.0, rel_tol=1e-9)  # type: ignore[attr-defined]

    def test_gee_asl_1_1(self, sanctar: object) -> None:
        """Reference: geeASL = 1.1 g."""
        assert math.isclose(sanctar.gee_asl, 1.1, rel_tol=1e-9)  # type: ignore[attr-defined]

    def test_mu_approximately_4_8424e12(self, sanctar: object) -> None:
        """Reference: mu ~ 4.8424e12 m^3/s^2."""
        assert math.isclose(sanctar.mu, 4.8424e12, rel_tol=1e-3)  # type: ignore[attr-defined]

    def test_mu_exact_formula(self, sanctar: object) -> None:
        """mu must equal gee_asl * G0 * radius^2 exactly."""
        from kopdeltav.models import G0

        expected = 1.1 * G0 * 670_000.0**2
        assert math.isclose(sanctar.mu, expected, rel_tol=1e-9)  # type: ignore[attr-defined]
