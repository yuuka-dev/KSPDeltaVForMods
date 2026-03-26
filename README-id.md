[English](README.md) | [日本語](README-ja.md)

# KSPDeltaVForMods

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

> Kalkulator delta-v untuk mod planet pack KSP1 berbasis Kopernicus

## Gambaran Umum

KSPDeltaVForMods mem-parsing file `.cfg` Kopernicus dan menghitung nilai delta-v mekanika orbital termasuk peluncuran ke orbit, transfer Hohmann, pembakaran lepas, dan rasio massa dengan pemodelan atmosfer lengkap.

### Mengapa dibuat?

Peta delta-v tersedia untuk KSP vanilla, tetapi tidak untuk mod planet pack. Jika Anda memasang planet pack seperti Celestial Harmony, tidak ada referensi berapa banyak delta-v yang dibutuhkan untuk mencapai orbit atau transfer antar planet. Alat ini membaca file konfigurasi Kopernicus dari mod dan menghitung semuanya secara otomatis.

## Fitur Utama

- **Parser Kopernicus ConfigNode** -- Menangani modifier, komentar, nested node, dan kunci AnimationCurve
- **Mesin Perhitungan Delta-V** -- Peluncuran ke orbit, transfer Hohmann, kecepatan lepas, persamaan roket Tsiolkovsky
- **Pemodelan Atmosfer** -- Interpolasi cubic Hermite spline yang kompatibel dengan AnimationCurve KSP
- **CLI Interaktif** -- Navigasi pohon benda langit dan hitung rute antar benda langit
- **Pemindai GameData** -- Memindai direktori GameData KSP secara rekursif dan menyimpan data yang di-parse sebagai JSON

## Tumpukan Teknologi

| Lapisan | Teknologi | Catatan |
|---------|-----------|---------|
| Library Inti | Python 3.10+ | Tanpa dependensi eksternal |
| CLI | Python standalone | `python run.py` -- tidak perlu pip install |
| Backend API | FastAPI + Uvicorn | Direncanakan |
| Frontend | Vue 3 + Vite + TypeScript | Direncanakan |
| Desktop | Tauri v2 (Rust) | Direncanakan |

## Memulai

### Prasyarat

- Python 3.10 atau lebih baru

### Penggunaan

```bash
git clone https://github.com/yuuka-dev/KSPDeltaVForMods.git
cd KSPDeltaVForMods
python run.py --scan /path/to/KSP/GameData
python run.py --interactive
```

Anda juga dapat menghitung delta-v untuk satu file konfigurasi:

```bash
python run.py sample_configs/Sanctar.cfg
```

## Catatan KSP2

Alat ini hanya menargetkan KSP1 + Kopernicus. KSP2 tidak didukung dan tidak ada rencana untuk mendukungnya.

## Lisensi

[MIT](LICENSE)
