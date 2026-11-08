![BRINGAS CUT](assets/header.svg)

![Windows](https://img.shields.io/badge/Windows-10%2F11-0078D6)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![ffmpeg](https://img.shields.io/badge/ffmpeg-required-009900)
![GPU](https://img.shields.io/badge/GPU-NVENC%20%2F%20QSV%20%2F%20AMF-76B900)
![License](https://img.shields.io/badge/License-MIT-green)

# ✂ BRINGAS CUT

**HYDRA TEAM BRINGAS • PERMUDAH HIDUPMU**

Cincang 1 video jadi banyak klip. Audio asli **dibuang total** di semua klip.
Tiap klip dikasih **1 efek random yang beda dari klip lain**. Nama file output
**acak**, bukan `klip_01`, `klip_02` — jadi urutan asli klip tidak ketahuan.

> **Catatan jujur:** efek acak bikin tiap klip makin beda dari video aslinya,
> jadi lebih susah dikenali fingerprint otomatis. Tapi **TIDAK ADA jaminan
> 100% lolos** Content ID atau review reused-content YouTube — apalagi buat
> monetisasi, reviewer manusia bisa tetap menolak konten yang cuma potongan
> orang lain tanpa nilai tambah. Tool ini paling aman dipakai buat footage
> sendiri / stock / berizin, atau sebagai B-roll yang nanti ditambah narasi
> original.

## Setup 1 Klik (untuk yang awam)

Double-click **`setup-1-klik.bat`**, tunggu sampai ada tulisan `SELESAI`, beres.

Yang dilakukan otomatis, berurutan:

1. **[1/4] Cek Python.** Kalau belum ada, install otomatis (coba `winget` dulu,
   kalau gagal download installer Python 3.12 dari python.org lalu install silent).
2. **[2/4] Cek ffmpeg.exe + ffprobe.exe.** Kalau belum ada, download otomatis
   dari gyan.dev lalu taruh di folder ini (sebelah .exe nanti).
3. **[3/4] Install PyInstaller** otomatis (pip).
4. **[4/4] Build `BringasCut.exe`** otomatis, lalu dibuka.

Yang lo butuhkan cuma: **Windows 10/11 + internet**. Tidak perlu install Python
manual, tidak perlu centang "Add Python to PATH" manual. Tidak butuh admin.

Kalau internet lambat, download ffmpeg (~100 MB) bisa 3-5 menit — itu normal,
bukan stuck. Download pakai `curl` dulu (retry otomatis 3x), kalau gagal baru
fallback ke PowerShell dengan timeout dimatikan (`-TimeoutSec 0`).

Alternatif: jalankan **`run.bat`** (cek Python + ffmpeg, lalu buka GUI dari
source), atau **`build_exe.bat`** (build `.exe` saja, tanpa setup Python/ffmpeg).

> `ffmpeg.exe` + `ffprobe.exe` **TIDAK** dibundel ke dalam `.exe`. Taruh di folder
> yang sama dengan `BringasCut.exe`, atau di PATH.

## Cara Pakai

1. Buka `BringasCut.exe` (atau `run.bat`).
2. **1 — Video:** Browse 1 file video lokal (`.mp4`, `.mov`, `.mkv`, `.avi`,
   `.webm`). Tidak ada download dari YouTube — siapkan file videonya dulu.
3. **2 — Potong & Efek:**
   - **Min / Max durasi klip (detik):** default Min **3**, Max **8**. Tiap klip
     durasinya diacak di antara Min-Max. Isi semaunya lo (Min minimal 1 detik).
   - **Intensitas efek:** `Lembut banget` (paling halus), `Lembut` (default),
     `Guncang` (paling kuat).
4. **3 — Preview & Output:** klik **Lihat Rencana Potongan (Preview)** buat
   lihat jumlah klip + durasi + efek tiap klip sebelum render. Pilih folder
   output (default `Videos/BringasCut`).
5. Klik **✂ POTONG**. Tunggu sampai ada tulisan `SELESAI` + jumlah klip.

Contoh: video 5 menit (300 detik), Min 3 / Max 8 → sekitar **40-55 klip**,
tiap klip 3-8 detik, efek beda-beda, nama file acak kayak `a7k9x2q4m1.mp4`.

## Fitur

- **Cincang acak:** durasi tiap klip random uniform di [Min, Max].
- **Sisa akhir digabung:** kalau sisa di ujung video < Min, sisa itu digabung
  ke klip terakhir (klip terakhir bisa sampai Max + Min). Tidak pernah ada
  klip mungil < Min — kecuali videonya sendiri lebih pendek dari Min, maka
  jadinya 1 klip = video utuh.
- **Audio dibuang total:** semua klip `-an`, tidak ada sisa suara asli.
- **8 efek, diundi tanpa pengulangan dini:** `Zoom In`, `Zoom Out`,
  `Zoom Napas` (masuk-keluar), `Pan Kiri`, `Pan Kanan`, `Pan Atas`,
  `Guncang Lembut`, `Zoom + Guncang`. Pool 8 efek di-shuffle, dipakai semua
  baru boleh ulang (reshuffle tiap siklus), dan **tidak ada 2 klip berurutan
  yang efeknya sama** — termasuk di perbatasan siklus.
- **Nama output acak:** 10 karakter `[a-z0-9]` + `.mp4` (mis. `a7k9x2q4m1.mp4`).
  Tabrakan nama di folder output → nama baru diregenerasi. Tidak ada
  `klip_01`, `klip_02`.
- **Kualitas bagus:** resolusi + fps asli dipertahankan, re-encode per klip.
  CPU: libx264 CRF 18 preset veryfast. GPU (kalau terdeteksi): NVENC p4 + CQ 19,
  Quick Sync medium + ICQ 19, AMF balanced + CQP 19. Checkbox
  "Pakai GPU kalau tersedia" (default ON) + label status di seksi Video.
- **Sikat aja:** render sukses = ffmpeg exit 0 + file output ada. Tidak ada
  langkah verifikasi yang bisa menggagalkan render yang sudah selesai.
- **Tanpa jendela cmd hitam:** semua ffmpeg/ffprobe jalan dengan
  `CREATE_NO_WINDOW` di Windows.
- **UI dark neon** ala HYDRA TEAM BRINGAS, jendela bisa di-scroll, log terminal
  hijau.

## Detail teknis

- **Efek pakai filter `zoompan`** (filter kanonik ffmpeg buat zoom halus).
  Percobaan pertama pakai `scale` + `crop` dengan ukuran crop berubah per
  waktu **GAGAL**: `crop` w/h dievaluasi sekali di awal filter, jadi `t` di
  w/h ditolak ffmpeg ("Error when evaluating the expression"). `zoompan`
  mengevaluasi z/x/y per frame, jadi semua 8 efek jalan di sana.
  - Zoom: `z` naik dari 1 ke zoom_max (in), turun dari zoom_max ke 1 (out),
    atau napas `1 + (max-1)*(0.5 - 0.5*cos(2*pi*on/N))`.
  - Pan: zoom ditahan di tengah, jendela geser linear.
  - Guncang: offset `sin`/`cos` di x/y, amplitudo di-clamp ke margin jendela
    (`min(amp, margin/2*0.9)`) supaya jendela tidak pernah keluar frame.
  - `on` = nomor frame output (mulai 0 tiap klip, karena tiap klip 1 panggilan
    ffmpeg sendiri), `N` = total frame klip.
- **Intensitas** (zoom_max / shake_amp px di lebar 1920 / frekuensi goyang):

  | Intensitas | Zoom max | Shake | Freq |
  |---|---|---|---|
  | Lembut banget | 1.06 | 5 px | 1.2 Hz |
  | Lembut | 1.12 | 10 px | 1.6 Hz |
  | Guncang | 1.20 | 22 px | 2.8 Hz |

  Shake diskalakan proporsional buat lebar video lain.
- **GPU:** deteksi dari `ffmpeg -encoders` + **verifikasi tiap kandidat
  dengan encode 1-frame**. Daftar `-encoders` saja bukan bukti — NVENC
  terdaftar walau tanpa GPU NVIDIA. Deteksi sekali per ffmpeg (cache).
- **Probe durasi:** rantai fallback format duration → stream duration →
  frames/fps (sama kayak Bringas Render PC). Input yang durasi/resolusinya
  tidak terbaca ditolak dengan error, bukan ditebak.
- **Tiap klip 1 panggilan ffmpeg:** `-ss START -t DUR -i INPUT -vf <efek> -an
  <encoder> -movflags +faststart OUTPUT`.

## File

| File | Isi |
|---|---|
| `bringas_cut.py` | GUI Tkinter (video picker, Min/Max, intensitas, GPU, preview, POTONG) |
| `ffmpeg_utils.py` | Logika inti: probe, GPU, efek (zoompan), plan klip, nama acak, render |
| `test_logic.py` | Self-test (logika + integrasi ffmpeg), jalankan `python3 test_logic.py` |
| `setup-1-klik.bat` | Setup 1 klik: Python + ffmpeg + PyInstaller + build .exe |
| `build_exe.bat` | Build `BringasCut.exe` saja (PyInstaller) |
| `run.bat` | Jalankan GUI dari source |
| `requirements.txt` | Stdlib only, tanpa dependensi pihak ketiga |
| `assets/header.svg` | Header animasi gradasi cyan-magenta-ungu |
| `LICENSE` | MIT |

## Test

```bash
python3 test_logic.py
```

**v1: 277 passed, 0 failed** — termasuk tes integrasi ffmpeg: video tes 10 detik
640x360 + audio dibuat di tempat, dicincang (Min 3 / Max 5), 3 klip di-render
dengan efek berbeda, dicek file ada, durasi ≈ rencana, resolusi tetap 640x360,
dan **tidak ada audio stream** di klip hasil. Semua 24 kombinasi
(8 efek × 3 intensitas) juga sudah di-render sekali dan lolos.

## Catatan v1

- Windows app, Python Tkinter stdlib-only + ffmpeg (pola yang sama kayak
  Bringas Render PC, tapi codebase terpisah — bukan fork/ubah Bringas Render).
- Nama tool + repo: **Bringas Cut**, `ilyasahmadalmaki/bringas-cut`.
- Repo GitHub harus dibuat manual oleh user (GitHub App tidak bisa bikin repo,
  403) — lalu push folder ini ke `main`.
- Yang belum ada di v1: batch banyak file sekaligus (1 video per jalan),
  potong ikut scene, dan progress per klip dalam persen (baru log + bar
  indeterminate).
