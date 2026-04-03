//! Multilingual translation system for CLI and backend output.
//!
//! Provides translation lookup by dot-notation keys with fallback to English
//! and then to the key itself. Supports Japanese, English, and Indonesian.
//!
//! 多言語翻訳モジュール。

use std::collections::HashMap;

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/// Supported language codes.
pub const SUPPORTED_LANGUAGES: &[&str] = &["ja", "en", "id"];

/// Default UI language.
pub const DEFAULT_LANGUAGE: &str = "ja";

// ---------------------------------------------------------------------------
// Translation data
// ---------------------------------------------------------------------------

/// Build the complete translation table for a given language.
///
/// 指定言語の翻訳テーブルを構築する。
fn build_translations(lang: &str) -> HashMap<&'static str, &'static str> {
    match lang {
        "ja" => build_ja(),
        "en" => build_en(),
        "id" => build_id(),
        _ => HashMap::new(),
    }
}

fn build_ja() -> HashMap<&'static str, &'static str> {
    let mut m = HashMap::new();
    // nav
    m.insert("nav.title", "KSPDeltaVForMods");
    m.insert("nav.bodies", "天体一覧");
    // body
    m.insert("body.name", "天体名");
    m.insert("body.radius", "半径");
    m.insert("body.radius_short", "半径");
    m.insert("body.mass", "質量");
    m.insert("body.gravity", "表面重力");
    m.insert("body.atmosphere", "大気");
    m.insert("body.has_atmosphere", "大気あり");
    m.insert("body.no_atmosphere", "大気なし");
    m.insert("body.has_ocean", "海洋あり");
    m.insert("body.no_ocean", "海洋なし");
    // launch
    m.insert("launch.title", "低軌道投入\u{0394}V");
    m.insert("launch.orbital_velocity", "軌道速度");
    m.insert("launch.gravity_loss", "重力損失");
    m.insert("launch.drag_loss", "大気抵抗損失");
    m.insert("launch.total_ideal", "理論最小\u{0394}V");
    m.insert("launch.total_rocket", "ロケット\u{0394}V\u{ff08}実用値\u{ff09}");
    m.insert("launch.jet_savings", "ジェット節約分");
    m.insert("launch.total_with_jets", "ジェット併用\u{0394}V");
    m.insert("launch.target_altitude", "目標高度");
    m.insert("launch.geostationary", "静止軌道遷移");
    m.insert("launch.geostationary_altitude", "静止軌道高度");
    // hohmann
    m.insert("hohmann.title", "ホーマン遷移");
    m.insert("hohmann.departure_dv", "出発\u{0394}V");
    m.insert("hohmann.arrival_dv", "到着\u{0394}V");
    m.insert("hohmann.total_dv", "合計\u{0394}V");
    m.insert("hohmann.transfer_time", "遷移時間");
    // tsiolkovsky
    m.insert("tsiolkovsky.title", "ツィオルコフスキーの公式");
    m.insert("tsiolkovsky.mass_ratio", "質量比");
    m.insert("tsiolkovsky.fuel_fraction", "燃料割合");
    m.insert("tsiolkovsky.dry_mass", "乾燥質量");
    m.insert("tsiolkovsky.fuel_mass", "燃料質量");
    m.insert("tsiolkovsky.delta_v", "\u{0394}V");
    m.insert("tsiolkovsky.isp", "比推力");
    m.insert("tsiolkovsky.wet_mass", "湿潤質量");
    // atmosphere
    m.insert("atmosphere.title", "大気プロファイル");
    m.insert("atmosphere.depth", "大気高度上限");
    m.insert("atmosphere.sea_level_pressure", "海面気圧");
    m.insert("atmosphere.sea_level_temperature", "海面温度");
    m.insert("atmosphere.sea_level_density", "海面大気密度");
    m.insert("atmosphere.molar_mass", "モル質量");
    m.insert("atmosphere.adiabatic_index", "断熱指数");
    // common
    m.insert("common.calculate", "計算");
    m.insert("common.reset", "リセット");
    m.insert("common.error", "エラー");
    m.insert("common.warning", "警告");
    m.insert("common.unit_m", "m");
    m.insert("common.unit_ms", "m/s");
    m.insert("common.unit_s", "秒");
    m.insert("common.unit_kg", "kg");
    m.insert("common.unit_kgm3", "kg/m\u{b3}");
    m.insert("common.unit_kpa", "kPa");
    m.insert("common.unit_k", "K");
    // route
    m.insert("route.launch", "低軌道投入");
    m.insert("route.escape", "母星脱出");
    m.insert("route.transfer", "惑星間遷移");
    m.insert("route.orbit_insertion", "軌道投入");
    m.insert("route.landing", "着陸");
    m.insert("route.moon_transfer", "衛星遷移");
    m.insert("route.moon_landing", "衛星着陸");
    m.insert("route.system_escape", "恒星系脱出");
    m.insert("route.third_cosmic", "第三宇宙速度");
    m.insert("route.powered_landing", "パワード着陸");
    m.insert("route.aerobrake_landing", "エアロブレーキ着陸");
    m.insert("route.cumulative", "累積\u{0394}V");
    m.insert("route.step", "ステップ");
    m.insert("route.dv", "\u{0394}V");
    m.insert("route.total", "合計");
    // system
    m.insert("system.home_world", "母星");
    m.insert("system.star", "恒星");
    m.insert("system.planets", "惑星一覧");
    m.insert("system.moons", "衛星一覧");
    m.insert("system.select_destination", "遷移先を選択");
    m.insert("system.select_moon", "衛星を選択");
    m.insert("system.press_enter_escape", "Enterで恒星系脱出");
    m.insert("system.press_enter_land", "Enterで着陸");
    m.insert("system.no_bodies", "天体が見つかりません");
    m.insert("system.scanning", "GameDataをスキャン中...");
    // error
    m.insert("error.file_not_found", "ファイルが見つかりません");
    m.insert("error.parse_error", "設定ファイルの解析に失敗しました");
    m.insert("error.no_bodies", "天体が見つかりません");
    m.insert("error.invalid_altitude", "高度は非負でなければなりません");
    m
}

fn build_en() -> HashMap<&'static str, &'static str> {
    let mut m = HashMap::new();
    // nav
    m.insert("nav.title", "KSPDeltaVForMods");
    m.insert("nav.bodies", "Celestial Bodies");
    // body
    m.insert("body.name", "Body Name");
    m.insert("body.radius", "Radius");
    m.insert("body.radius_short", "R");
    m.insert("body.mass", "Mass");
    m.insert("body.gravity", "Surface Gravity");
    m.insert("body.atmosphere", "Atmosphere");
    m.insert("body.has_atmosphere", "Has Atmosphere");
    m.insert("body.no_atmosphere", "No Atmosphere");
    m.insert("body.has_ocean", "Has Ocean");
    m.insert("body.no_ocean", "No Ocean");
    // launch
    m.insert("launch.title", "Launch to Low Orbit \u{0394}V");
    m.insert("launch.orbital_velocity", "Orbital Velocity");
    m.insert("launch.gravity_loss", "Gravity Loss");
    m.insert("launch.drag_loss", "Drag Loss");
    m.insert("launch.total_ideal", "Theoretical Minimum \u{0394}V");
    m.insert("launch.total_rocket", "Rocket \u{0394}V (Practical)");
    m.insert("launch.jet_savings", "Jet Engine Savings");
    m.insert("launch.total_with_jets", "\u{0394}V with Jets");
    m.insert("launch.target_altitude", "Target Altitude");
    m.insert("launch.geostationary", "Geostationary Transfer");
    m.insert("launch.geostationary_altitude", "Geostationary Altitude");
    // hohmann
    m.insert("hohmann.title", "Hohmann Transfer");
    m.insert("hohmann.departure_dv", "Departure \u{0394}V");
    m.insert("hohmann.arrival_dv", "Arrival \u{0394}V");
    m.insert("hohmann.total_dv", "Total \u{0394}V");
    m.insert("hohmann.transfer_time", "Transfer Time");
    // tsiolkovsky
    m.insert("tsiolkovsky.title", "Tsiolkovsky Rocket Equation");
    m.insert("tsiolkovsky.mass_ratio", "Mass Ratio");
    m.insert("tsiolkovsky.fuel_fraction", "Fuel Fraction");
    m.insert("tsiolkovsky.dry_mass", "Dry Mass");
    m.insert("tsiolkovsky.fuel_mass", "Fuel Mass");
    m.insert("tsiolkovsky.delta_v", "\u{0394}V");
    m.insert("tsiolkovsky.isp", "Specific Impulse");
    m.insert("tsiolkovsky.wet_mass", "Wet Mass");
    // atmosphere
    m.insert("atmosphere.title", "Atmosphere Profile");
    m.insert("atmosphere.depth", "Atmosphere Ceiling");
    m.insert("atmosphere.sea_level_pressure", "Sea Level Pressure");
    m.insert("atmosphere.sea_level_temperature", "Sea Level Temperature");
    m.insert("atmosphere.sea_level_density", "Sea Level Density");
    m.insert("atmosphere.molar_mass", "Molar Mass");
    m.insert("atmosphere.adiabatic_index", "Adiabatic Index");
    // common
    m.insert("common.calculate", "Calculate");
    m.insert("common.reset", "Reset");
    m.insert("common.error", "Error");
    m.insert("common.warning", "Warning");
    m.insert("common.unit_m", "m");
    m.insert("common.unit_ms", "m/s");
    m.insert("common.unit_s", "s");
    m.insert("common.unit_kg", "kg");
    m.insert("common.unit_kgm3", "kg/m\u{b3}");
    m.insert("common.unit_kpa", "kPa");
    m.insert("common.unit_k", "K");
    // route
    m.insert("route.launch", "Launch to Low Orbit");
    m.insert("route.escape", "Escape Home World");
    m.insert("route.transfer", "Interplanetary Transfer");
    m.insert("route.orbit_insertion", "Orbit Insertion");
    m.insert("route.landing", "Landing");
    m.insert("route.moon_transfer", "Moon Transfer");
    m.insert("route.moon_landing", "Moon Landing");
    m.insert("route.system_escape", "Star System Escape");
    m.insert("route.third_cosmic", "Third Cosmic Velocity");
    m.insert("route.powered_landing", "Powered Landing");
    m.insert("route.aerobrake_landing", "Aerobrake Landing");
    m.insert("route.cumulative", "Cumulative \u{0394}V");
    m.insert("route.step", "Step");
    m.insert("route.dv", "\u{0394}V");
    m.insert("route.total", "Total");
    // system
    m.insert("system.home_world", "Home World");
    m.insert("system.star", "Star");
    m.insert("system.planets", "Planets");
    m.insert("system.moons", "Moons");
    m.insert("system.select_destination", "Select destination");
    m.insert("system.select_moon", "Select moon");
    m.insert("system.press_enter_escape", "Press Enter for system escape");
    m.insert("system.press_enter_land", "Press Enter to land");
    m.insert("system.no_bodies", "No celestial bodies found");
    m.insert("system.scanning", "Scanning GameData...");
    // error
    m.insert("error.file_not_found", "File not found");
    m.insert("error.parse_error", "Failed to parse configuration file");
    m.insert("error.no_bodies", "No celestial bodies found");
    m.insert("error.invalid_altitude", "Altitude must be non-negative");
    m
}

fn build_id() -> HashMap<&'static str, &'static str> {
    let mut m = HashMap::new();
    // nav
    m.insert("nav.title", "KSPDeltaVForMods");
    m.insert("nav.bodies", "Daftar Benda Langit");
    // body
    m.insert("body.name", "Nama Benda Langit");
    m.insert("body.radius", "Radius");
    m.insert("body.radius_short", "R");
    m.insert("body.mass", "Massa");
    m.insert("body.gravity", "Gravitasi Permukaan");
    m.insert("body.atmosphere", "Atmosfer");
    m.insert("body.has_atmosphere", "Memiliki Atmosfer");
    m.insert("body.no_atmosphere", "Tanpa Atmosfer");
    m.insert("body.has_ocean", "Memiliki Lautan");
    m.insert("body.no_ocean", "Tanpa Lautan");
    // launch
    m.insert("launch.title", "\u{0394}V Peluncuran ke Orbit Rendah");
    m.insert("launch.orbital_velocity", "Kecepatan Orbit");
    m.insert("launch.gravity_loss", "Kehilangan Gravitasi");
    m.insert("launch.drag_loss", "Kehilangan Hambatan Udara");
    m.insert("launch.total_ideal", "\u{0394}V Minimum Teoritis");
    m.insert("launch.total_rocket", "\u{0394}V Roket (Praktis)");
    m.insert("launch.jet_savings", "Penghematan Mesin Jet");
    m.insert("launch.total_with_jets", "\u{0394}V dengan Jet");
    m.insert("launch.target_altitude", "Ketinggian Target");
    m.insert("launch.geostationary", "Transfer Geostasioner");
    m.insert("launch.geostationary_altitude", "Ketinggian Geostasioner");
    // hohmann
    m.insert("hohmann.title", "Transfer Hohmann");
    m.insert("hohmann.departure_dv", "\u{0394}V Keberangkatan");
    m.insert("hohmann.arrival_dv", "\u{0394}V Kedatangan");
    m.insert("hohmann.total_dv", "\u{0394}V Total");
    m.insert("hohmann.transfer_time", "Waktu Transfer");
    // tsiolkovsky
    m.insert("tsiolkovsky.title", "Persamaan Roket Tsiolkovsky");
    m.insert("tsiolkovsky.mass_ratio", "Rasio Massa");
    m.insert("tsiolkovsky.fuel_fraction", "Fraksi Bahan Bakar");
    m.insert("tsiolkovsky.dry_mass", "Massa Kering");
    m.insert("tsiolkovsky.fuel_mass", "Massa Bahan Bakar");
    m.insert("tsiolkovsky.delta_v", "\u{0394}V");
    m.insert("tsiolkovsky.isp", "Impuls Spesifik");
    m.insert("tsiolkovsky.wet_mass", "Massa Basah");
    // atmosphere
    m.insert("atmosphere.title", "Profil Atmosfer");
    m.insert("atmosphere.depth", "Batas Ketinggian Atmosfer");
    m.insert("atmosphere.sea_level_pressure", "Tekanan Permukaan Laut");
    m.insert("atmosphere.sea_level_temperature", "Suhu Permukaan Laut");
    m.insert("atmosphere.sea_level_density", "Kepadatan Permukaan Laut");
    m.insert("atmosphere.molar_mass", "Massa Molar");
    m.insert("atmosphere.adiabatic_index", "Indeks Adiabatik");
    // common
    m.insert("common.calculate", "Hitung");
    m.insert("common.reset", "Atur Ulang");
    m.insert("common.error", "Kesalahan");
    m.insert("common.warning", "Peringatan");
    m.insert("common.unit_m", "m");
    m.insert("common.unit_ms", "m/s");
    m.insert("common.unit_s", "s");
    m.insert("common.unit_kg", "kg");
    m.insert("common.unit_kgm3", "kg/m\u{b3}");
    m.insert("common.unit_kpa", "kPa");
    m.insert("common.unit_k", "K");
    // route
    m.insert("route.launch", "Peluncuran ke Orbit Rendah");
    m.insert("route.escape", "Lepas dari Planet Asal");
    m.insert("route.transfer", "Transfer Antarplanet");
    m.insert("route.orbit_insertion", "Penyisipan Orbit");
    m.insert("route.landing", "Pendaratan");
    m.insert("route.moon_transfer", "Transfer Bulan");
    m.insert("route.moon_landing", "Pendaratan Bulan");
    m.insert("route.system_escape", "Lepas dari Sistem Bintang");
    m.insert("route.third_cosmic", "Kecepatan Kosmis Ketiga");
    m.insert("route.powered_landing", "Pendaratan Berdaya");
    m.insert("route.aerobrake_landing", "Pendaratan Aerobrake");
    m.insert("route.cumulative", "\u{0394}V Kumulatif");
    m.insert("route.step", "Langkah");
    m.insert("route.dv", "\u{0394}V");
    m.insert("route.total", "Total");
    // system
    m.insert("system.home_world", "Planet Asal");
    m.insert("system.star", "Bintang");
    m.insert("system.planets", "Planet");
    m.insert("system.moons", "Bulan");
    m.insert("system.select_destination", "Pilih tujuan");
    m.insert("system.select_moon", "Pilih bulan");
    m.insert(
        "system.press_enter_escape",
        "Tekan Enter untuk lepas dari sistem",
    );
    m.insert("system.press_enter_land", "Tekan Enter untuk mendarat");
    m.insert("system.no_bodies", "Tidak ada benda langit ditemukan");
    m.insert("system.scanning", "Memindai GameData...");
    // error
    m.insert("error.file_not_found", "Berkas tidak ditemukan");
    m.insert("error.parse_error", "Gagal mengurai berkas konfigurasi");
    m.insert("error.no_bodies", "Tidak ada benda langit ditemukan");
    m.insert("error.invalid_altitude", "Ketinggian harus non-negatif");
    m
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/// Get translated text by dot-notation key.
///
/// 翻訳文字列を取得する。要求言語にキーがなければ英語にフォールバックし、
/// 英語にもなければキー文字列をそのまま返す。
///
/// # Arguments
/// * `key` - Dot-notation key (e.g. "launch.title", "common.calculate").
/// * `lang` - Language code ("ja", "en", or "id"). Falls back to English
///   if the key is missing in the requested language.
///
/// # Returns
/// Translated string. Returns the key itself if not found in any language.
pub fn get_text(key: &str, lang: &str) -> String {
    let effective_lang = if SUPPORTED_LANGUAGES.contains(&lang) {
        lang
    } else {
        DEFAULT_LANGUAGE
    };

    // Key must be "category.name" format
    if !key.contains('.') {
        return key.to_string();
    }

    // Try requested language first
    let translations = build_translations(effective_lang);
    if let Some(value) = translations.get(key) {
        return (*value).to_string();
    }

    // Fall back to English
    if effective_lang != "en" {
        let en_translations = build_translations("en");
        if let Some(value) = en_translations.get(key) {
            return (*value).to_string();
        }
    }

    // Key not found anywhere: return the key itself
    key.to_string()
}

/// Get all translation keys flattened to dot-notation for a language.
///
/// 全翻訳キーをフラット化して返す。
///
/// # Arguments
/// * `lang` - Language code ("ja", "en", or "id"). Falls back to DEFAULT_LANGUAGE
///   if not supported.
///
/// # Returns
/// HashMap mapping dot-notation keys to translated strings.
pub fn get_all_keys(lang: &str) -> HashMap<String, String> {
    let effective_lang = if SUPPORTED_LANGUAGES.contains(&lang) {
        lang
    } else {
        DEFAULT_LANGUAGE
    };

    build_translations(effective_lang)
        .into_iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect()
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_get_text_japanese() {
        assert_eq!(get_text("nav.title", "ja"), "KSPDeltaVForMods");
    }

    #[test]
    fn test_get_text_english() {
        assert_eq!(get_text("nav.bodies", "en"), "Celestial Bodies");
    }

    #[test]
    fn test_get_text_indonesian() {
        assert_eq!(get_text("nav.bodies", "id"), "Daftar Benda Langit");
    }

    #[test]
    fn test_get_text_fallback_to_default_then_english() {
        // Unsupported lang falls back to DEFAULT_LANGUAGE ("ja") first
        // "nav.title" is "KSPDeltaVForMods" in all languages
        assert_eq!(get_text("nav.title", "xx"), "KSPDeltaVForMods");
    }

    #[test]
    fn test_get_text_unknown_key_returns_key() {
        assert_eq!(get_text("unknown.key", "en"), "unknown.key");
    }

    #[test]
    fn test_get_all_keys_has_entries() {
        let keys = get_all_keys("en");
        assert!(keys.contains_key("nav.title"));
        assert!(keys.contains_key("launch.title"));
    }

    #[test]
    fn test_get_all_keys_unsupported_lang_uses_default() {
        let keys = get_all_keys("xx");
        // Should fall back to Japanese (DEFAULT_LANGUAGE)
        assert_eq!(keys.get("nav.bodies").unwrap(), "天体一覧");
    }

    #[test]
    fn test_get_text_no_dot_returns_key() {
        assert_eq!(get_text("nodotkey", "en"), "nodotkey");
    }

    #[test]
    fn test_all_three_languages_have_same_keys() {
        let ja_keys: Vec<String> = get_all_keys("ja").keys().cloned().collect();
        let en_keys = get_all_keys("en");
        let id_keys = get_all_keys("id");
        for key in &ja_keys {
            assert!(
                en_keys.contains_key(key),
                "English missing key: {}",
                key
            );
            assert!(
                id_keys.contains_key(key),
                "Indonesian missing key: {}",
                key
            );
        }
    }

    #[test]
    fn test_japanese_specific_values() {
        assert_eq!(get_text("common.calculate", "ja"), "計算");
        assert_eq!(get_text("common.reset", "ja"), "リセット");
        assert_eq!(get_text("hohmann.title", "ja"), "ホーマン遷移");
    }

    #[test]
    fn test_english_specific_values() {
        assert_eq!(get_text("common.calculate", "en"), "Calculate");
        assert_eq!(get_text("hohmann.title", "en"), "Hohmann Transfer");
    }

    #[test]
    fn test_indonesian_specific_values() {
        assert_eq!(get_text("common.calculate", "id"), "Hitung");
        assert_eq!(get_text("hohmann.title", "id"), "Transfer Hohmann");
    }
}
