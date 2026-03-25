from __future__ import annotations

from kopdeltav.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, get_all_keys, get_text


class TestGetText:
    def test_japanese_key(self) -> None:
        assert get_text("launch.title", "ja") == "低軌道投入ΔV"

    def test_english_key(self) -> None:
        assert get_text("launch.title", "en") == "Launch to Low Orbit ΔV"

    def test_dot_notation(self) -> None:
        assert get_text("common.calculate", "ja") == "計算"
        assert get_text("common.calculate", "en") == "Calculate"

    def test_missing_key_returns_key(self) -> None:
        assert get_text("nonexistent.key", "ja") == "nonexistent.key"

    def test_missing_name_returns_key(self) -> None:
        assert get_text("launch.nonexistent", "ja") == "launch.nonexistent"

    def test_no_dot_returns_key(self) -> None:
        assert get_text("nodot", "ja") == "nodot"

    def test_invalid_lang_falls_back(self) -> None:
        result = get_text("launch.title", "fr")
        assert result == get_text("launch.title", DEFAULT_LANGUAGE)

    def test_default_lang_is_ja(self) -> None:
        assert get_text("launch.title") == "低軌道投入ΔV"

    def test_nav_category(self) -> None:
        assert get_text("nav.title", "ja") == "KSPDeltaVForMods"
        assert get_text("nav.bodies", "en") == "Celestial Bodies"

    def test_body_category(self) -> None:
        assert get_text("body.name", "ja") == "天体名"
        assert get_text("body.radius", "en") == "Radius"

    def test_launch_category(self) -> None:
        assert get_text("launch.orbital_velocity", "ja") == "軌道速度"
        assert get_text("launch.total_rocket", "en") == "Rocket ΔV (Practical)"

    def test_hohmann_category(self) -> None:
        assert get_text("hohmann.title", "ja") == "ホーマン遷移"
        assert get_text("hohmann.total_dv", "en") == "Total ΔV"

    def test_tsiolkovsky_category(self) -> None:
        assert get_text("tsiolkovsky.title", "ja") == "ツィオルコフスキーの公式"
        assert get_text("tsiolkovsky.mass_ratio", "en") == "Mass Ratio"

    def test_atmosphere_category(self) -> None:
        assert get_text("atmosphere.title", "ja") == "大気プロファイル"
        assert get_text("atmosphere.depth", "en") == "Atmosphere Ceiling"

    def test_common_category(self) -> None:
        assert get_text("common.error", "ja") == "エラー"
        assert get_text("common.warning", "en") == "Warning"

    def test_error_category(self) -> None:
        assert get_text("error.file_not_found", "ja") == "ファイルが見つかりません"
        assert get_text("error.parse_error", "en") == "Failed to parse configuration file"


class TestGetAllKeys:
    def test_returns_flat_dict(self) -> None:
        result = get_all_keys("ja")
        assert isinstance(result, dict)
        assert all("." in k for k in result)

    def test_all_keys_present_ja(self) -> None:
        result = get_all_keys("ja")
        assert "launch.title" in result
        assert "common.calculate" in result
        assert "error.file_not_found" in result

    def test_all_keys_present_en(self) -> None:
        result = get_all_keys("en")
        assert "launch.title" in result
        assert "common.calculate" in result
        assert "error.file_not_found" in result

    def test_ja_and_en_have_same_keys(self) -> None:
        ja_keys = set(get_all_keys("ja").keys())
        en_keys = set(get_all_keys("en").keys())
        assert ja_keys == en_keys

    def test_invalid_lang_falls_back(self) -> None:
        result = get_all_keys("fr")
        expected = get_all_keys(DEFAULT_LANGUAGE)
        assert result == expected


class TestConstants:
    def test_supported_languages(self) -> None:
        assert "ja" in SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES

    def test_default_language(self) -> None:
        assert DEFAULT_LANGUAGE == "ja"
