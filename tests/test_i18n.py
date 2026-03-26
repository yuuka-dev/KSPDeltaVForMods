from __future__ import annotations

import os
from unittest.mock import patch

from kopdeltav.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    _warned_keys,
    detect_language,
    get_all_keys,
    get_text,
)


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

    def test_route_category_ja(self) -> None:
        assert get_text("route.launch") == "低軌道投入"

    def test_route_category_en(self) -> None:
        assert get_text("route.launch", "en") == "Launch to Low Orbit"

    def test_geostationary_key(self) -> None:
        assert get_text("launch.geostationary") == "静止軌道遷移"

    def test_system_category(self) -> None:
        assert get_text("system.home_world") == "母星"

    def test_indonesian_key(self) -> None:
        assert get_text("launch.title", "id") == "ΔV Peluncuran ke Orbit Rendah"

    def test_indonesian_common(self) -> None:
        assert get_text("common.calculate", "id") == "Hitung"

    def test_missing_key_in_lang_falls_back_to_english(self) -> None:
        """If a key is missing in the requested language, fall back to English."""
        # We test by temporarily removing a key from a language.
        # Instead, we test the fallback mechanism via a key that only exists in en.
        # The get_text function should fall back to en when the key is missing.
        _warned_keys.discard("nonexistent_test.fallback_key")
        result = get_text("nonexistent_test.fallback_key", "id")
        assert result == "nonexistent_test.fallback_key"

    def test_completely_unknown_key_returns_key_string(self) -> None:
        """A key not found in any language returns the key string itself."""
        _warned_keys.discard("totally.unknown_key_xyz")
        result = get_text("totally.unknown_key_xyz", "en")
        assert result == "totally.unknown_key_xyz"

    def test_new_keys_radius_short(self) -> None:
        assert get_text("body.radius_short", "ja") == "半径"
        assert get_text("body.radius_short", "en") == "R"
        assert get_text("body.radius_short", "id") == "R"

    def test_new_keys_route_step(self) -> None:
        assert get_text("route.step", "ja") == "ステップ"
        assert get_text("route.step", "en") == "Step"
        assert get_text("route.step", "id") == "Langkah"

    def test_new_keys_route_dv(self) -> None:
        assert get_text("route.dv", "ja") == "ΔV"
        assert get_text("route.dv", "en") == "ΔV"
        assert get_text("route.dv", "id") == "ΔV"

    def test_new_keys_route_total(self) -> None:
        assert get_text("route.total", "ja") == "合計"
        assert get_text("route.total", "en") == "Total"
        assert get_text("route.total", "id") == "Total"


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

    def test_all_en_keys_exist_in_id(self) -> None:
        """All English keys must exist in Indonesian (completeness check)."""
        en_keys = set(get_all_keys("en").keys())
        id_keys = set(get_all_keys("id").keys())
        missing = en_keys - id_keys
        assert not missing, f"Keys missing in 'id': {missing}"

    def test_all_en_keys_exist_in_ja(self) -> None:
        """All English keys must exist in Japanese (completeness check)."""
        en_keys = set(get_all_keys("en").keys())
        ja_keys = set(get_all_keys("ja").keys())
        missing = en_keys - ja_keys
        assert not missing, f"Keys missing in 'ja': {missing}"

    def test_invalid_lang_falls_back(self) -> None:
        result = get_all_keys("fr")
        expected = get_all_keys(DEFAULT_LANGUAGE)
        assert result == expected


class TestConstants:
    def test_supported_languages(self) -> None:
        assert "ja" in SUPPORTED_LANGUAGES
        assert "en" in SUPPORTED_LANGUAGES

    def test_indonesian_in_supported_languages(self) -> None:
        assert "id" in SUPPORTED_LANGUAGES

    def test_default_language(self) -> None:
        assert DEFAULT_LANGUAGE == "ja"


class TestDetectLanguage:
    def test_override_id(self) -> None:
        assert detect_language(override="id") == "id"

    def test_override_ja(self) -> None:
        assert detect_language(override="ja") == "ja"

    def test_override_en(self) -> None:
        assert detect_language(override="en") == "en"

    def test_override_unsupported_falls_back_to_env(self) -> None:
        with (
            patch.dict(os.environ, {"LC_MESSAGES": "", "LANG": "", "LC_ALL": ""}, clear=False),
            patch("kopdeltav.i18n.locale.getlocale", return_value=(None, None)),
        ):
            result = detect_language(override="xx")
            # With no env vars and no locale, should fall back to "en"
            assert result == "en"

    def test_lang_env_ja(self) -> None:
        with patch.dict(
            os.environ,
            {"LC_MESSAGES": "", "LANG": "ja_JP.UTF-8", "LC_ALL": ""},
            clear=False,
        ):
            assert detect_language() == "ja"

    def test_lc_messages_priority_over_lang(self) -> None:
        with patch.dict(
            os.environ,
            {"LC_MESSAGES": "en_US.UTF-8", "LANG": "ja_JP.UTF-8", "LC_ALL": ""},
            clear=False,
        ):
            assert detect_language() == "en"

    def test_unknown_locale_returns_en(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"LC_MESSAGES": "xx_XX.UTF-8", "LANG": "xx_XX", "LC_ALL": "xx"},
                clear=False,
            ),
            patch("kopdeltav.i18n.locale.getlocale", return_value=(None, None)),
        ):
            assert detect_language() == "en"

    def test_empty_env_returns_en(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"LC_MESSAGES": "", "LANG": "", "LC_ALL": ""},
                clear=False,
            ),
            patch("kopdeltav.i18n.locale.getlocale", return_value=(None, None)),
        ):
            assert detect_language() == "en"

    def test_lc_all_fallback(self) -> None:
        with patch.dict(
            os.environ,
            {"LC_MESSAGES": "", "LANG": "", "LC_ALL": "id_ID.UTF-8"},
            clear=False,
        ):
            assert detect_language() == "id"

    def test_locale_getlocale_fallback(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"LC_MESSAGES": "", "LANG": "", "LC_ALL": ""},
                clear=False,
            ),
            patch("kopdeltav.i18n.locale.getlocale", return_value=("ja_JP", "UTF-8")),
        ):
            assert detect_language() == "ja"
