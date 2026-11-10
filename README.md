<p align="center"><img src="assets/bringas-cut-logo.png" alt="Logo Bringas Cut" width="200"></p>

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
> 100% lolos** Content ID atau review reused-content YouTube.

## Setup 1 Klik (untuk yang awam)

Double-click **`setup-1-klik.bat`**, tunggu sampai ada tulisan `SELESAI`, beres.

Yang dilakukan otomatis, berurutan:

1. **[1/5] Cek Python.** Kalau belum ada, install otomatis (coba `winget` dulu,
   kalau gagal download installer Python 3.12 dari python.org lalu install silent).
2. **[2/5] Cek ffmpeg.exe + ffprobe.exe.** Kalau belum ada, download otomatis
   dari gyan.dev lalu taruh di folder ini (sebelah .exe nanti).
3. **[3/5] Cek yt-dlp.exe** (buat download dari YouTube). Kalau belum ada,
   download otomatis dari GitHub releases lalu taruh di folder ini.
4. **[4/5] Install PyInstaller** otomatis (pip).
5. **[5/5] Build `BringasCut.exe`** otomatis, lalu dibuka.

Yang lo butuhkan cuma: **Windows 10/11 + internet**. Tidak perlu install Python
manual, tidak perlu centang "Add Python to PATH" manual. Tidak butuh admin.

Kalau internet lambat, download ffmpeg (~100 MB) bisa 3-5 menit — itu normal,
bukan stuck. Download pakai `curl` dulu (retry otomatis 3x), kalau gagal baru
fallback ke PowerShell dengan timeout dimatikan (`-TimeoutSec 0`).

Alternatif: jalankan **`run.bat`** (cek Python + ffmpeg, lalu buka GUI dari
source), atau **`build_exe.bat`** (build `.exe` saja, tanpa setup Python/ffmpeg).

> `ffmpeg.exe` + `ffprobe.exe` + `yt-dlp.exe` **TIDAK** dibundel ke dalam `.exe`.
> Taruh di folder yang sama dengan `BringasCut.exe`, atau di PATH.

## Cara Pakai

1. Buka `BringasCut.exe` (atau `run.bat`).
2. **1 — Sumber Video (v1.2): 2 opsi.**
   - **File lokal:** Browse 1 file video (`.mp4`, `.mov`, `.mkv`, `.avi`, `.webm`).
   - **Download dari YouTube:** tempel URL video (`youtube.com/watch`,
     `youtube.com/shorts/`, `youtu.be/`, `music.youtube.com`), klik
     **Cek Info** buat lihat judul + durasi + **kualitas max video**
     dulu (v1.3: mis. "kualitas max 240p — download jadi 240p", jadi
     ketahuan sebelum download kalau videonya memang mentok rendah),
     atau langsung **⬇ Download**. Kualitas download: **1080p terbaik
     (HD biasa, bukan "1080p Premium")** — format terbaik dengan tinggi
     ≤ 1080 (kalau sumbernya 4K, diambil 1080-nya; kalau sumber max
     720p, diambil 720p), **bitrate tertinggi di resolusi itu** (v1.6),
     hasil akhir **wajib .mp4**. v1.5 memakai **default yt-dlp** (tanpa
     memaksa client) — sama kayak ytDownloader.
     File hasil download tersimpan di `folder output/downloads/` dengan
     nama = judul video, lalu otomatis jadi sumber potongan. Kalau klik
     **✂ POTONG** saat URL sudah ditempel tapi belum di-download,
     download jalan dulu otomatis baru cincang.
   - Satu video saja, **bukan playlist**. **Cookies dari browser (v1.4,
     opt-in):** kalau YouTube cuma ngasih 360p / nge-blok (SABR, bot-check),
     centang "Pakai cookies dari browser" lalu pilih browser lo (Chrome /
     Edge / Firefox / Brave / Opera / Vivaldi). yt-dlp jalan pakai sesi
     login browser lo — YouTube ngasih format lengkap sampai 1080p. Default
     mati; cookies dibaca lokal oleh yt-dlp, tidak dikirim ke mana-mana.
     Dengan cookies, video private / age-restricted bisa di-download kalau
     akun lo punya akses; tanpa cookies tidak bisa.
   - ⚠️ **Download hanya untuk video milik sendiri / yang kamu punya hak
     pakainya.** Download dari YouTube dapat melanggar Ketentuan Layanan
     YouTube.
3. **2 — Potong & Efek:**
   - **Min / Max durasi klip (detik):** default Min **3**, Max **8**. Tiap klip
     durasinya diacak di antara Min-Max. Isi semaunya lo (Min minimal 1 detik).
   - **Intensitas efek:** `Lembut banget` (paling halus), `Lembut` (default),
     `Guncang` (paling kuat).
   - **Efek tambahan (v1.1, seksi 3):** 3 checkbox, default ON semua —
     `Mirror flip` (50% klip di-flip, teks jadi kebalik di klip yang ke-flip),
     `Speed acak 0.92–1.08x` (durasi klip berubah ±8%),
     `Rotate miring acak 0.5–2°` (di-crop biar tidak ada sudut hitam).
     Bisa dimatikan satu-satu; kalau ketiganya mati, hasilnya sama persis
     dengan v1.
4. **4 — Preview & Output:** klik **Lihat Rencana Potongan (Preview)** buat
   lihat jumlah klip + durasi + efek tiap klip (termasuk efek tambahannya)
   sebelum render. Pilih folder output (default `Videos/BringasCut`).
5. Klik **✂ POTONG**. Tunggu sampai ada tulisan `SELESAI` + jumlah klip.

Contoh: video 5 menit (300 detik), Min 3 / Max 8 → sekitar **40-55 klip**,
tiap klip 3-8 detik, efek beda-beda, nama file acak kayak `a7k9x2q4m1.mp4`.

## Fitur

- **Download YouTube (v1.2, baru):** sumber video 2 opsi — File lokal atau
  Download dari YouTube via yt-dlp. Kualitas **1080p terbaik** (lihat
  "Cara Pakai" di atas), hasil akhir wajib `.mp4`, tidak pernah di atas
  1080p. Progress download tampil di log (tiap 5%). File hasil download
  tersimpan di `folder output/downloads/` (nama = judul video, anti-timpa
  gaya `(1)`, `(2)`). yt-dlp dicari di sebelah aplikasi dulu, lalu di PATH;
  kalau tidak ketemu, GUI menyuruh jalankan `setup-1-klik.bat` lagi —
  yt-dlp tidak pernah di-download diam-diam saat render. **Cookies dari
  browser (v1.4, opt-in):** checkbox + pilih browser — yt-dlp pakai
  `--cookies-from-browser` biar YouTube ngasih format 1080p lengkap saat
  tanpa cookies cuma dapat 360p (SABR / bot-check). **Tidak didukung:**
  playlist, live, video private / age-restricted tanpa cookies.
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
- **Efek tambahan v1.1 (opsional, di atas efek utama):**
  - **Mirror flip** — tiap klip punya peluang 50% di-flip kiri-kanan
    (bukan semua klip, supaya tidak semua teks kebalik dan polanya tidak
    monoton). Paling kuat ngacak fingerprint visual.
  - **Speed acak 0.92–1.08x** — tiap klip dapat speed acak (2 desimal),
    diterapkan via `setpts`. Durasi output klip = durasi rencana / speed,
    jadi berubah **±8%** (mis. rencana 4.0s di 1.08x jadi ~3.7s).
    Log per klip menampilkan durasi rencana → durasi output.
  - **Rotate miring acak 0.5–2°** — tiap klip dapat sudut acak (besar
    0.5–2.0°, arah + / - acak). Di-render dengan overscale ~1.08x dulu
    lalu crop tengah, jadi **tidak ada sudut hitam** di pojok.
  - Urutan filter per klip: efek utama (`zoompan`) → rotate → flip →
    speed (`setpts` saja) → `format yuv420p`. Resolusi + fps output
    tetap = asli. Ketiganya bisa dimatikan satu-satu di GUI; kalau semua
    mati, hasil identik dengan v1.
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
- **Efek tambahan v1.1** (`roll_extra_effects` + `build_extra_filter`,
  di `ffmpeg_utils.py`):
  - Roll per klip, independen: flip = koin 50%, speed = uniform
    0.92–1.08 (2 desimal), rotate = tanda ± acak × uniform 0.5–2.0°
    (1 desimal). Semua OFF → string filter `""`, `render_clip` tidak
    mengubah rantai filter (hasil = v1).
  - Rotate: `scale` 1.08x dulu → `rotate` (radian, `fillcolor=black`) →
    `crop` tengah ke WxH asli. 1.08 cukup buat nutupin sudut di ≤2°
    buat rasio aspek apa pun (kasus terburuk butuh ~1.067 di 16:9, dari
    `1/(cos - (W/H)*sin)`).
  - Speed: `setpts=PTS/speed` saja — **tanpa** filter `fps` sesudahnya.
    Terverifikasi 2026-11-09: `setpts` + `fps=30` setelah `zoompan`
    merusak klip (duplikasi frame ~512x — klip 3.7 detik jadi 56.888
    frame / 31 menit; `start_time=0` tidak memperbaikinya). `setpts`
    saja sudah benar (2.0 detik di 1.08x → 56 frame, 1.87 detik,
    `avg_frame_rate` tetap 30/1) karena muxer MP4 (vsync CFR default)
    yang menormalkan frame rate. Durasi output = rencana / speed.
  - Chain lengkap per klip: `zoompan,rotate,hflip,setpts,format`.
- **Download YouTube v1.2** (`is_youtube_url` + `build_ytdlp_command` +
  `parse_ytdlp_progress` + `find_yt_dlp` + `download_youtube_video`,
  di `ffmpeg_utils.py`):
  - URL diterima: `youtube.com/watch`, `/shorts/`, `/embed/`, `/live/`,
    `/v/`, `music.youtube.com`, `youtu.be/<id>` (boleh tanpa `https://`).
    Domain lain, URL kosong, dan `/playlist` ditolak dengan pesan jelas.
    URL playlist yang ada `v=`-nya tetap jalan — yt-dlp `--no-playlist`
    hanya download video itu saja.
  - Format string: `bv*[height<=1080][ext=mp4][format_note!*=?Premium]+ba[ext=m4a]/bv*[height<=1080][format_note!*=?Premium]+ba/b[height<=1080][ext=mp4][format_note!*=?Premium]/b[height<=1080][format_note!*=?Premium]`
    + `--merge-output-format mp4`. Artinya: video terbaik ≤1080p dulu
    (utamakan mp4), audio terbaik, lalu di-merge ke `.mp4`. Filter
    `format_note!*=?Premium` (v1.5) mengecualikan format "1080p Premium"
    (itag 616/235) — tanpa langganan Premium format itu gagal
    di-download, dan yt-dlp malah mengutamakannya (source_preference
    +100) kalau tidak difilter; target app adalah 1080p HD biasa.
  - Format sort (v1.6): `--format-sort res,br` di semua command yt-dlp
    (info + download) — resolusi dulu, lalu bitrate. Sort default yt-dlp
    mengutamakan codec (av01 > vp9 > avc1) sebelum bitrate, jadi
    "bestvideo" 1080p yang dipilih adalah AV1 470 kbps (itag 399);
    dengan `res,br`, yang dipilih adalah 1080p bitrate tertinggi
    (270, AVC 2221 kbps di video tes).
  - Player client (v1.5): **tidak ada `--extractor-args`** — pakai default
    yt-dlp, sama kayak ytDownloader. Dulu (v1.2–v1.4) dipaksa
    `android,web`, dan client android ternyata kena batasan SABR:
    terbukti 2026-11-10 dari PC user, `yt-dlp -F` tanpa extractor args
    nunjukin daftar lengkap sampai 1080p (137/270/614/248/399),
    sementara `android,web` cuma ngasih format 18 (360p).
  - **Cookies (v1.4, opt-in):** `cookies_args` + `--cookies-from-browser
    <browser>` (chrome / edge / firefox / brave / opera / vivaldi) ke Cek
    Info dan download — dengan sesi login, YouTube ngasih format lengkap
    sampai 1080p walau tanpa cookies cuma dapat 360p (SABR / bot-check).
  - **Hasil selalu .mp4 (v1.4):** kalau yt-dlp menulis `.mkv`/`.webm`,
    `remux_to_mp4` me-remux ke `.mp4` tanpa re-encode (`-c copy`); gagal
    remux → file aslinya dipakai + peringatan di log.
  - Nama file download = judul video yang di-sanitize (karakter ilegal →
    `_`, spasi → `_`, max 120 char) + `.mp4`, di `folder output/downloads/`,
    anti-timpa `(1)`, `(2)`. Template yt-dlp `Judul.%(ext)s` dipakai supaya
    path hasil deterministic buat caller.
  - Progress: yt-dlp jalan dengan `--newline`, output digabung
    (stdout+stderr) dan di-parse live (`[download] 45.2% ...` → 45.2);
    callback dipanggil tiap naik ≥5% atau 100%. Sukses = yt-dlp exit 0 +
    file `.mp4` ada dan tidak 0 byte. Gagal → 5 baris terakhir output
    ditampilkan sebagai error (mis. video private / butuh login).
  - Tanpa jendela cmd hitam: `CREATE_NO_WINDOW` juga buat yt-dlp.
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
| `bringas_cut.py` | GUI Tkinter (video picker, Min/Max, intensitas, efek tambahan, GPU, preview, POTONG) |
| `ffmpeg_utils.py` | Logika inti: probe, GPU, efek (zoompan) + efek tambahan v1.1 (flip/speed/rotate), plan klip, nama acak, render |
| `test_logic.py` | Self-test (logika + integrasi ffmpeg), jalankan `python3 test_logic.py` |
| `setup-1-klik.bat` | Setup 1 klik: Python + ffmpeg + yt-dlp + PyInstaller + build .exe |
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

**v1.1: ditambah tes efek tambahan** — roll flip ~50% (seed 42 = tepat 50/100),
speed dalam [0.92, 1.08], |rotate| dalam [0.5, 2.0] dengan arah +/-, string
filter (urutan rotate → hflip → setpts, `""` kalau semua mati), dan integrasi
ffmpeg: 5 klip (flip saja, speed 1.08x, speed 0.92x, rotate 2.0°, kombinasi
flip+speed+rotate) dicek durasi ≈ rencana/speed, resolusi tetap, tanpa audio —
plus bukti piksel: frame klip flip **benar-benar beda** dari frame klip polos,
dan `extras=None` menghasilkan durasi = rencana (perilaku v1). Total v1.1: **326 passed, 0 failed**.

**v1.2: ditambah tes download YouTube** — `is_youtube_url` (watch / shorts /
youtu.be / music / embed / live diterima; vimeo / facebook / tiktok / playlist /
URL kosong ditolak), `youtube_url_problem` (pesan khusus playlist), command
yt-dlp (format cap `height<=1080`, merge mp4, `--no-playlist`, `--newline`,
extractor-args `android,web`), `parse_ytdlp_progress` (45.2% / 2.4% / 100% /
baris non-progress → None), `find_yt_dlp` (explicit / PATH mock / None kalau
tidak ada), sanitize + penomoran `(1)` + `download_target_path`, info video
dan download via **yt-dlp palsu** (skrip tiruan: info, progress 50% + 100%,
gagal → error tail), alur lengkap fake-download → cincang 1 klip, dan
**download YouTube beneran** di VM ini: video publik "Me at the zoo" (19 detik)
judul + durasi terbaca, file `.mp4` hasil download ada, tinggi ≤ 1080, sumber
punya audio. Total v1.2: **410 passed, 0 failed**.

**v1.3: Cek Info tampilkan kualitas max + logo resmi** — `get_youtube_info`
baca daftar format via `yt-dlp -J`
(`_heights_from_formats`: max video + terbaik ≤1080p), GUI menampilkan
"kualitas max Xp — download jadi Yp" plus catatan "video ini mentok Xp,
bukan salah tool" kalau max < 1080p; fallback ke judul+durasi lama kalau
JSON gagal. Tes: fake yt-dlp jawab `-J` (240p-only), 3 cek heights baru
(4K → 2160/1080, 240-only → 240/240, tanpa video → None/None), tes
integrasi YouTube beneran nambah cek max 240p buat 'Me at the zoo'.
Logo resmi (gunting neon motong strip film) jadi icon jendela + icon
`.exe` + tampil di atas README ini. Total di VM ini: **423 passed,
0 failed** (tes integrasi YouTube beneran skip karena yt-dlp tidak ada
di VM ini).

**v1.4: cookies dari browser + hasil download selalu .mp4** — checkbox
cookies (default mati) + pilih browser, diteruskan sebagai
`--cookies-from-browser` ke Cek Info dan download (`cookies_args`:
normalisasi nama, browser tidak dikenal → tanpa cookies, bukan error).
Hasil download yang bukan `.mp4` (mis. `.mkv`/`.webm`) di-remux ke `.mp4`
tanpa re-encode (`remux_to_mp4`, `-c copy`); kalau remux gagal, file
aslinya tetap dipakai + peringatan di log. Tes: 26 cek baru — cookies
(command / info palsu / download palsu), remux mkv→mp4 beneran (video +
audio ikut), remux gagal (src hilang / ffmpeg bogus / src sampah), dan
download palsu .mkv → hasil akhir `.mp4` (file `.mkv` dihapus) + fallback
remux-gagal. Total di VM ini: **449 passed, 0 failed** (tes integrasi
YouTube beneran skip karena yt-dlp tidak ada di VM ini).

**v1.5: default yt-dlp + kecualikan Premium + error asli** — `--extractor-args`
dihapus dari semua command yt-dlp (Cek Info + download); format string
dapat filter `[format_note!*=?Premium]` di tiap pilihan video;
`get_youtube_info` gagal mengembalikan `{"error": ...}` berisi ekor stderr
yt-dlp yang asli (bukan None), dan GUI menampilkannya di dialog Cek Info /
download. Tes: 5 cek baru — command tanpa `--extractor-args` / android,
format mengandung filter Premium, selector yt-dlp offline (string lama
pilih `616+140`, string baru pilih `137+140`, cuma-18 tetap `18`), info
palsu gagal → dict error. Total di VM ini: **454 passed, 0 failed** (tes
integrasi YouTube beneran skip karena yt-dlp tidak ada di VM ini).

**v1.6: format sort bitrate tertinggi** — `--format-sort res,br` di semua
command yt-dlp (download + Cek Info); tes: 4 cek baru — format-sort ada
di command download + info, selector offline (sort default pilih
`399+140`, sort `res,br` pilih `270+140`). Total di VM ini:
**458 passed, 0 failed** (tes integrasi YouTube beneran skip karena
yt-dlp tidak ada di VM ini).

## Catatan v1.6

- **Masalah (laporan user 2026-11-11):** "jelek banget bitrate nya" —
  v1.5 download 1080p tapi bitrate-nya kecil. Penyebab: sort default
  yt-dlp mengutamakan codec sebelum bitrate, jadi yang dipilih adalah
  format 399 (AV1 1080p, cuma 470 kbps, ~10,6 MB buat video 3:10).
  Terverifikasi offline dengan daftar format lengkap dari screenshot
  `-F` user: sort default → `399+140`, sort `res,br` → `270+140`.
- **Perbaikan:** `--format-sort res,br` — resolusi dulu (tetap mentok
  1080p, tidak bocor ke 4K karena format string membatasi tinggi),
  lalu bitrate tertinggi di resolusi itu. Di video Velvet Room:
  270 (AVC 2221 kbps, ~50 MB) + audio m4a terbaik. Premium tetap
  dikecualikan (v1.5), default yt-dlp tetap dipakai (v1.5), cookies
  tetap opt-in (v1.4).

## Catatan v1.5

- **Bukti dari PC user (2026-11-10 malam):** screenshot `yt-dlp -F` untuk
  video Velvet Room nunjukin daftar lengkap sampai 1080p (137 mp4 1080p,
  270, 614 vp9, 248 webm, 399 av01, plus 616 "1080p Premium") — tanpa
  extractor args. Sementara `android,web` (v1.2–v1.4) di video yang sama
  cuma ngasih format 18 (360p). Jadi yang bikin mentok 360p adalah
  pemaksaan client android (SABR), bukan format selector-nya.
- **Kenapa Premium dikecualikan:** itag 616/235 dapat `source_preference
  +100` dari yt-dlp, jadi tanpa filter, selector lama memilih `616+140`
  — dan format itu butuh langganan Premium, gagal di-download kalau tidak
  Premium. Terverifikasi offline (selector yt-dlp 2026.10.26):
  string lama → `616+140`, string v1.5 → `137+140`.
- **Cookies (v1.4) tetap ada sebagai opsi** (opt-in, default mati) buat
  jaringan yang kena bot-check total — tapi bukan lagi jalan utama.
  Kalau Cek Info gagal, dialog sekarang nunjukin error asli yt-dlp
  (mis. "Sign in to confirm you're not a bot" / 429), bukan pesan generik.

## Catatan v1.4

- **Kenapa 360p, kenapa cookies:** YouTube ke IP yang ke-blok cuma ngasih
  format rendah lewat client Android (SABR) dan client Web gagal (429 /
  bot-check / PO token) — format selector sebagus apa pun tidak bisa
  mengambil 1080p kalau daftar formatnya cuma sampai 360p. Cookies dari
  browser bikin yt-dlp jalan dengan sesi login, jadi YouTube ngasih
  format lengkap. Cara ini sama dengan yang dipakai downloader populer
  ytDownloader (10,6k stars) — kodenya tidak dicopas (lisensi beda:
  ytDownloader GPL-3.0, repo ini MIT), idenya yang dipakai.
- **Hasil download selalu .mp4:** kalau yt-dlp menulis `.mkv`/`.webm`,
  app me-remux ke `.mp4` tanpa re-encode (kualitas tidak turun).
  Kalau remux gagal, file aslinya tetap dipakai — download tidak
  digagalkan cuma gara-gara container.
- Spek lain tidak berubah: satu video, bukan playlist, 1080p terbaik,
  tanpa login/cookies kalau checkbox mati.

## Catatan v1.2

- Sumber video sekarang 2 opsi: File lokal (perilaku lama, tidak berubah) dan
  Download dari YouTube (baru). Download kualitas **1080p terbaik** — format
  terbaik ≤1080p, hasil akhir wajib `.mp4`. Kalau sumbernya cuma 720p, yang
  di-download 720p (yang terbaik yang ada); kalau sumbernya 4K, diambil
  1080-nya, bukan 4K.
- yt-dlp **tidak** dibundel ke repo (sama kayak ffmpeg) — `setup-1-klik.bat`
  download `yt-dlp.exe` dari GitHub releases. Kalau yt-dlp tidak ketemu, GUI
  menampilkan pesan jelas, bukan crash.
- **Yang tidak didukung:** playlist, live. Video private / age-restricted
  butuh cookies dari browser (v1.4); tanpa cookies akan gagal dengan pesan
  error yt-dlp apa adanya di log.
- **Catatan jaringan (jujur):** dari VM ini (IP proxy bersama), client web
  YouTube kena HTTP 429 / bot-check dan default yt-dlp (visionos) juga
  kena bot-check, jadi download memakai client android sebagai fallback
  di v1.2–v1.4 — dan client android bisa kena batasan SABR yang
  membatasi tinggi yang tersedia (video tes lama cuma dapat 360p). Di PC
  rumahan biasa, default yt-dlp menyediakan 1080p (terbukti 2026-11-10:
  daftar format lengkap sampai 1080p) — karena itu v1.5 memakai default
  dan tidak lagi memaksa android. Format string-nya sendiri sudah benar:
  ia selalu memilih yang terbaik ≤1080p dari format yang tersedia.
- **ToS:** download hanya untuk video milik sendiri / yang kamu punya hak
  pakainya. Download dari YouTube dapat melanggar Ketentuan Layanan YouTube.
- Pengingat jujur (tetap berlaku): efek tambahan bikin klip makin beda dari
  aslinya dan makin susah dicocokkan fingerprint, tapi **TIDAK ADA jaminan
  100% lolos** Content ID / review reused-content YouTube.

## Catatan v1.1

- 3 efek tambahan (flip / speed / rotate) default ON semua — pilihan user
  ("Cuma top 3 aja"). Bisa dimatikan satu-satu di seksi "3 — Efek tambahan".
- Speed mengubah durasi output klip ±8% — itu wajar, bukan bug. Log per klip
  menampilkan durasi rencana → durasi output (mis. `3.9s -> 3.7s`).
- Flip membalik teks di klip yang ke-flip — karena itu cuma 50% klip yang
  di-flip, bukan semuanya.
- Pengingat jujur (tetap berlaku): efek tambahan bikin klip makin beda dari
  aslinya dan makin susah dicocokkan fingerprint, tapi **TIDAK ADA jaminan
  100% lolos** Content ID / review reused-content YouTube.

## Catatan v1

- Windows app, Python Tkinter stdlib-only + ffmpeg (pola yang sama kayak
  Bringas Render PC, tapi codebase terpisah — bukan fork/ubah Bringas Render).
- Nama tool + repo: **Bringas Cut**, `ilyasahmadalmaki/bringas-cut`.
- Repo GitHub harus dibuat manual oleh user (GitHub App tidak bisa bikin repo,
  403) — lalu push folder ini ke `main`.
- Yang belum ada di v1: batch banyak file sekaligus (1 video per jalan),
  potong ikut scene, dan progress per klip dalam persen (baru log + bar
  indeterminate).
