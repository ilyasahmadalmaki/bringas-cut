"""
Bringas Cut — bringas_cut.py
Windows desktop tool (Python 3.10+ Tkinter, stdlib only).
Cincang 1 video jadi banyak klip, audio dibuang total, tiap klip
dikasih 1 efek random yang beda dari klip lain, nama file output acak.
v1.1: 3 efek tambahan opsional per klip — mirror flip (50%), speed
acak 0.92-1.08x, rotate miring acak 0.5-2 derajat — default ON semua.
v1.2: sumber video 2 opsi — File lokal atau Download dari YouTube
(via yt-dlp, kualitas 1080p terbaik, hasil .mp4).
v1.3: Cek Info nunjukin kualitas max video sebelum download, plus
logo resmi (icon jendela + icon .exe + README).

Jalankan:  python bringas_cut.py
           (atau double-click run.bat di Windows)
ffmpeg.exe + ffprobe.exe + yt-dlp.exe harus ada di folder aplikasi
atau di PATH (gyan.dev builds untuk ffmpeg; yt-dlp dari GitHub
releases — setup-1-klik.bat yang download semuanya).
"""
from __future__ import annotations

import os
import queue
import random
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Optional

import ffmpeg_utils as fu

# HYDRA TEAM BRINGAS — dark neon cyberpunk: near-black blue, cyan + magenta
BG = "#07090d"
PANEL = "#0e131c"
BORDER = "#22314a"
FG = "#e8f1ff"
MUTED = "#7d8aa3"
ACCENT = "#00e5ff"      # neon cyan — primary
ACCENT2 = "#ff2d95"     # neon magenta — secondary
WARN = "#f5a524"
OK = "#2ee59d"

VIDEO_EXTS = fu.VIDEO_EXTS

# v1.3 — logo resmi (gunting neon motong strip film).
LOGO_PNG_REL = Path("assets") / "bringas-cut-logo.png"


def resource_path(rel: Path) -> Path:
    """Path ke file aset: di dalam bundle PyInstaller (--add-data) file
    tinggal di sys._MEIPASS; kalau jalan dari source, relatif ke folder
    script ini. Dipakai buat icon jendela."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bringas Cut — HYDRA TEAM BRINGAS")
        self.geometry("980x820")
        self.configure(bg=BG)
        # v1.3 — logo resmi sebagai icon jendela. Gagal (file hilang /
        # Tk lama) = abaikan saja, app tetap jalan tanpa icon.
        self._icon_img = None
        try:
            _icon_path = resource_path(LOGO_PNG_REL)
            if _icon_path.is_file():
                self._icon_img = tk.PhotoImage(file=str(_icon_path))
                self.iconphoto(False, self._icon_img)
        except Exception:
            pass
        self.log_q: queue.Queue = queue.Queue()
        self.running = False
        self.ffmpeg_path = tk.StringVar(value=fu.find_ffmpeg())
        self.ffprobe_path = tk.StringVar(value=fu.find_ffprobe())

        # State — v1.2: sumber video 2 opsi (lokal / YouTube).
        self.source_mode = tk.StringVar(value="local")  # local | youtube
        self.video_file = tk.StringVar()
        self.yt_url = tk.StringVar()
        self.yt_downloaded = tk.StringVar()  # path file hasil download
        self.ytdlp_path = tk.StringVar(value=fu.find_yt_dlp() or "yt-dlp")
        self.min_dur = tk.StringVar(value="3")
        self.max_dur = tk.StringVar(value="8")
        self.intensity = tk.StringVar(value=fu.DEFAULT_INTENSITY)
        # v1.1 — extra effects, all ON by default (user's choice).
        self.flip_var = tk.BooleanVar(value=True)
        self.speed_var = tk.BooleanVar(value=True)
        self.rotate_var = tk.BooleanVar(value=True)
        self.out_folder = tk.StringVar(value=str(Path.home() / "Videos" / "BringasCut"))
        self.use_gpu_var = tk.BooleanVar(value=True)
        self._gpu_encoder = None
        # Probe cache (per session): probe each path once and reuse it.
        self._spec_cache: dict[str, fu.MediaInfo] = {}
        # Preview plan, reused by POTONG when settings did not change.
        self._planned_key = None
        self._planned = None  # (durations, effects, extras_list)

        self._build_ui()
        self.after(100, self._drain_log)

    # ------------------------------------------------------------------ UI
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("TFrame", background=BG)
        s.configure("TLabelframe", background=PANEL, foreground=FG,
                    bordercolor=BORDER, borderwidth=1)
        s.configure("TLabelframe.Label", background=PANEL, foreground=ACCENT,
                    font=("Segoe UI", 10, "bold"))
        s.configure("TLabel", background=PANEL, foreground=FG)
        s.configure("TCheckbutton", background=PANEL, foreground=FG,
                    indicatorcolor=ACCENT)
        s.configure("TButton", background="#131c2b", foreground=FG,
                    bordercolor=BORDER, borderwidth=1, padding=4)
        s.map("TButton",
              background=[("active", "#1e2c44"), ("disabled", "#0e131c")],
              foreground=[("disabled", MUTED)])
        s.configure("Accent.TButton", background=ACCENT, foreground="#02141a",
                    font=("Segoe UI", 12, "bold"), padding=10,
                    borderwidth=0)
        s.map("Accent.TButton",
              background=[("active", "#5ff0ff"), ("disabled", "#12303a")],
              foreground=[("disabled", "#5b7a86")])
        s.configure("TEntry", fieldbackground="#080c12", foreground=FG,
                    bordercolor=BORDER, insertcolor=ACCENT)
        s.configure("TCombobox", fieldbackground="#080c12", foreground=FG,
                    bordercolor=BORDER, insertcolor=ACCENT)
        s.configure("Horizontal.TProgressbar", background=ACCENT,
                    troughcolor="#080c12", bordercolor=BORDER, thickness=14)
        s.configure("Vertical.TScrollbar", background="#1c2942",
                    troughcolor="#080c12", arrowcolor=ACCENT,
                    bordercolor="#080c12")
        s.configure("TSeparator", background=ACCENT)

    def _build_ui(self):
        self._style()
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        root = ttk.Frame(canvas, padding=10)
        canvas.create_window((0, 0), window=root, anchor="nw", tags="main_window")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig("main_window", width=event.width)

        def _on_mousewheel(event):
            if getattr(event, "widget", None) is getattr(self, "log_text", None):
                return
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        root.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        title = tk.Label(root, text="✂ BRINGAS CUT",
                         font=("Consolas", 20, "bold"), bg=BG, fg=ACCENT)
        title.pack(anchor="w")
        tk.Label(root, text="HYDRA TEAM BRINGAS  •  PERMUDAH HIDUPMU",
                 font=("Consolas", 10, "bold"), bg=BG, fg=ACCENT2).pack(anchor="w", pady=(0, 2))
        tk.Label(root, text="Cincang video jadi banyak klip — audio dibuang total, tiap klip efek random beda, nama file acak",
                 bg=BG, fg=MUTED).pack(anchor="w", pady=(0, 8))
        ttk.Separator(root, orient="horizontal").pack(fill="x", pady=(0, 8))

        # ---- Sumber video (v1.2: 2 opsi) ----
        vf = ttk.LabelFrame(root, text="1 — Sumber Video", padding=8)
        vf.pack(fill="x", pady=4)
        ttk.Radiobutton(vf, text="File lokal",
                        variable=self.source_mode, value="local",
                        command=self._refresh_video_info).pack(anchor="w")
        row = ttk.Frame(vf); row.pack(fill="x", pady=2)
        ttk.Entry(row, textvariable=self.video_file, width=70).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self._pick_video_file).pack(side="left", padx=4)
        ttk.Radiobutton(vf, text="Download dari YouTube (yt-dlp, kualitas 1080p terbaik)",
                        variable=self.source_mode, value="youtube",
                        command=self._refresh_video_info).pack(anchor="w")
        row = ttk.Frame(vf); row.pack(fill="x", pady=2)
        ttk.Entry(row, textvariable=self.yt_url, width=70).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="⬇ Download", command=self._on_download_yt).pack(side="left", padx=4)
        ttk.Button(row, text="Cek Info", command=self._on_check_yt).pack(side="left", padx=4)
        self.yt_info = tk.Label(vf, text="Tempel URL video YouTube (watch / shorts / youtu.be), lalu Download.",
                                bg=PANEL, fg=MUTED, anchor="w")
        self.yt_info.pack(fill="x", pady=2)
        tk.Label(vf, text="Download hanya untuk video milik sendiri / yang kamu punya hak pakainya. Download dari YouTube dapat melanggar Ketentuan Layanan YouTube. Satu video saja, bukan playlist; tanpa login — video private / age-restricted tidak bisa di-download.",
                 bg=PANEL, fg=MUTED, wraplength=900, justify="left").pack(anchor="w")
        self.video_info = tk.Label(vf, text="Belum ada video dipilih.",
                                   bg=PANEL, fg=MUTED, anchor="w")
        self.video_info.pack(fill="x", pady=2)
        yt_row = ttk.Frame(vf)
        yt_row.pack(fill="x", pady=(2, 0))
        self.ytdlp_label = ttk.Label(yt_row, text="yt-dlp: mengecek…")
        self.ytdlp_label.pack(side="left")
        self._refresh_ytdlp_label()
        gpu_row = ttk.Frame(vf)
        gpu_row.pack(fill="x", pady=(2, 0))
        ttk.Checkbutton(gpu_row, text="Pakai GPU kalau tersedia (NVENC / Quick Sync / AMF)",
                        variable=self.use_gpu_var,
                        command=self._refresh_gpu_label).pack(side="left")
        self.gpu_label = ttk.Label(gpu_row, text="GPU: mengecek…")
        self.gpu_label.pack(side="left", padx=(8, 0))

        # ---- Potong ----
        cf = ttk.LabelFrame(root, text="2 — Potong & Efek", padding=8)
        cf.pack(fill="x", pady=4)
        row = ttk.Frame(cf); row.pack(fill="x", pady=2)
        tk.Label(row, text="Durasi klip (detik):  Min", bg=PANEL, fg=FG).pack(side="left")
        tk.Spinbox(row, from_=1, to=120, textvariable=self.min_dur,
                   width=5, bg="#080c12", fg=FG, insertbackground=ACCENT,
                   buttonbackground="#131c2b").pack(side="left", padx=4)
        tk.Label(row, text="Max", bg=PANEL, fg=FG).pack(side="left")
        tk.Spinbox(row, from_=1, to=300, textvariable=self.max_dur,
                   width=5, bg="#080c12", fg=FG, insertbackground=ACCENT,
                   buttonbackground="#131c2b").pack(side="left", padx=4)
        tk.Label(row, text=" (tiap klip durasinya diacak di antara Min-Max)",
                 bg=PANEL, fg=MUTED).pack(side="left")
        row = ttk.Frame(cf); row.pack(fill="x", pady=2)
        tk.Label(row, text="Intensitas efek:", bg=PANEL, fg=FG).pack(side="left")
        ttk.Combobox(row, textvariable=self.intensity,
                     values=list(fu.INTENSITIES), state="readonly",
                     width=16).pack(side="left", padx=4)
        tk.Label(row, text="Lembut banget = gerakan paling halus, Guncang = paling kuat",
                 bg=PANEL, fg=MUTED).pack(side="left")
        tk.Label(cf, text="Efek per klip diundi dari 8 efek (zoom in / zoom out / zoom napas / pan kiri / pan kanan / pan atas / guncang lembut / zoom+guncang) — pool diacak, dipakai semua baru boleh ulang, tidak ada 2 klip berurutan yang efeknya sama. Audio asli dibuang total di semua klip.",
                 bg=PANEL, fg=MUTED, wraplength=900, justify="left").pack(anchor="w", pady=(4, 0))

        # ---- Efek tambahan (v1.1) ----
        ef = ttk.LabelFrame(root, text="3 — Efek tambahan (opsional, di atas efek utama)", padding=8)
        ef.pack(fill="x", pady=4)
        ttk.Checkbutton(ef, text="Mirror flip — 50% klip di-flip (acak per klip). Teks jadi kebalik di klip yang ke-flip.",
                        variable=self.flip_var).pack(anchor="w")
        ttk.Checkbutton(ef, text="Speed acak 0.92–1.08x — durasi klip berubah ±8% (durasi output = rencana / speed).",
                        variable=self.speed_var).pack(anchor="w")
        ttk.Checkbutton(ef, text="Rotate miring acak 0.5–2° — di-crop biar tidak ada sudut hitam.",
                        variable=self.rotate_var).pack(anchor="w")
        tk.Label(ef, text="Ketiganya default ON (pilihan lo). Kalau ketiganya dimatikan, hasilnya sama persis dengan v1. Urutan filter per klip: efek utama → rotate → flip → speed → format.",
                 bg=PANEL, fg=MUTED, wraplength=900, justify="left").pack(anchor="w", pady=(4, 0))

        # ---- Preview + Output ----
        pf = ttk.LabelFrame(root, text="4 — Preview & Output", padding=8)
        pf.pack(fill="x", pady=4)
        ttk.Button(pf, text="Lihat Rencana Potongan (Preview)",
                   command=self._on_preview).pack(anchor="w")
        self.preview_label = tk.Label(pf, text="Preview: pilih video dulu.",
                                      bg=PANEL, fg=MUTED, anchor="w", justify="left")
        self.preview_label.pack(fill="x", pady=4)
        row = ttk.Frame(pf); row.pack(fill="x", pady=4)
        tk.Label(row, text="Folder output:", bg=PANEL, fg=FG).pack(side="left")
        ttk.Entry(row, textvariable=self.out_folder, width=55).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row, text="Browse…", command=self._pick_out_folder).pack(side="left")
        tk.Label(pf, text="Nama file output acak 10 karakter (mis. a7k9x2q4m1.mp4) — bukan klip_01, klip_02, jadi urutan asli klip tidak ketahuan. Kualitas: resolusi + fps asli dipertahankan, re-encode kualitas tinggi.",
                 bg=PANEL, fg=MUTED, wraplength=900, justify="left").pack(anchor="w")

        # ---- Settings ----
        sf = ttk.LabelFrame(root, text="Pengaturan ffmpeg / yt-dlp", padding=8)
        sf.pack(fill="x", pady=4)
        for label, var in (("ffmpeg:", self.ffmpeg_path), ("ffprobe:", self.ffprobe_path),
                           ("yt-dlp:", self.ytdlp_path)):
            r = ttk.Frame(sf); r.pack(fill="x", pady=1)
            tk.Label(r, text=label, bg=PANEL, fg=FG, width=9).pack(side="left")
            ttk.Entry(r, textvariable=var, width=70).pack(side="left", fill="x", expand=True)

        # ---- Run ----
        run = ttk.Frame(root); run.pack(fill="x", pady=6)
        self.btn_cut = ttk.Button(run, text="✂  POTONG", style="Accent.TButton",
                                  command=self._on_cut)
        self.btn_cut.pack(side="left", padx=2)
        self.btn_cancel = ttk.Button(run, text="Batalkan", command=self._on_cancel)
        self.btn_cancel.pack(side="left", padx=2)
        self.progress = ttk.Progressbar(run, mode="indeterminate", length=200)
        self.progress.pack(side="left", padx=8)

        self.log_text = tk.Text(root, height=10, bg="#04060a", fg="#39ff9d",
                                font=("Consolas", 9), insertbackground=ACCENT,
                                selectbackground="#123043", selectforeground=FG)
        self.log_text.pack(fill="both", expand=True, pady=4)
        tk.Label(root, text="◆ HYDRA TEAM BRINGAS — PERMUDAH HIDUPMU ◆",
                 font=("Consolas", 9, "bold"), bg=BG, fg=ACCENT2).pack(anchor="center", pady=(4, 0))
        self._log("Bringas Cut siap. Pilih sumber video (File lokal / Download YouTube), atur Min/Max + intensitas, lalu POTONG.")
        self._log("v1.2: download YouTube kualitas 1080p terbaik (yt-dlp) — file hasil download jadi .mp4 di folder output/downloads.")
        self._log("v1.1: efek tambahan flip / speed / rotate default ON (seksi 3) — matikan kalau tidak mau.")
        self._log("Catatan jujur: efek acak bikin klip makin beda dari aslinya, tapi TIDAK ADA jaminan 100% lolos Content ID / review reused-content YouTube.")
        self._log("Download YouTube hanya untuk video milik sendiri / yang kamu punya hak pakainya — download dapat melanggar Ketentuan Layanan YouTube.")
        self._detect_gpu()

    # ------------------------------------------------------------- logging
    def _log(self, msg: str):
        self.log_q.put(msg)

    def _drain_log(self):
        while True:
            try:
                msg = self.log_q.get_nowait()
            except queue.Empty:
                break
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            lines = int(self.log_text.index("end-1c").split(".")[0])
            if lines > 500:
                self.log_text.delete("1.0", "100.0")
        self.after(100, self._drain_log)

    # ------------------------------------------------------------- pickers
    def _pick_video_file(self):
        p = filedialog.askopenfilename(
            filetypes=[("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v")])
        if p:
            self.video_file.set(p)
            self.source_mode.set("local")
            self._planned_key = None
            self._refresh_video_info()

    def _pick_out_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.out_folder.set(p)

    # ------------------------------------------------------------- sumber video
    def _effective_video_path(self) -> str:
        """Video yang dipakai untuk preview/potong: file lokal, atau
        file hasil download YouTube (kalau sudah di-download)."""
        if self.source_mode.get() == "youtube":
            p = self.yt_downloaded.get()
            return p if p and os.path.isfile(p) else ""
        p = self.video_file.get()
        return p if p and os.path.isfile(p) else ""

    def _resolve_ytdlp(self) -> Optional[str]:
        """yt-dlp dari kolom pengaturan, atau hasil pencarian otomatis."""
        typed = self.ytdlp_path.get().strip()
        if typed and typed != "yt-dlp":
            if os.path.isfile(typed):
                return typed
        found = fu.find_yt_dlp(typed if typed and typed != "yt-dlp" else None)
        return found

    def _refresh_ytdlp_label(self):
        found = self._resolve_ytdlp()
        if found:
            self.ytdlp_label.config(text=f"yt-dlp: ketemu ({os.path.basename(found)})")
        else:
            self.ytdlp_label.config(
                text="yt-dlp: TIDAK ketemu — jalankan setup-1-klik.bat lagi untuk download yt-dlp.exe")

    def _download_yt_sync(self, url: str, out_dir: str) -> str:
        """Download 1 video YouTube (blocking, dipanggil dari worker
        thread): cek info dulu, lalu download ke <out_dir>/downloads.
        Return path file .mp4 hasil download. Raise RuntimeError kalau
        gagal (pesan error yt-dlp disertakan)."""
        log = self._log
        problem = fu.youtube_url_problem(url)
        if problem:
            raise RuntimeError(problem)
        ytdlp = self._resolve_ytdlp()
        if not ytdlp:
            raise RuntimeError("yt-dlp tidak ketemu — jalankan setup-1-klik.bat "
                               "lagi untuk download yt-dlp.exe.")
        log(f"Download YouTube: {url}")
        info = fu.get_youtube_info(ytdlp, url)
        if info is None:
            raise RuntimeError("yt-dlp gagal membaca info video — mungkin video "
                               "private / age-restricted / butuh login, atau "
                               "YouTube memblokir permintaan dari IP ini "
                               "(coba lagi nanti / dari jaringan lain).")
        title = info["title"]
        dur = info["duration"]
        dur_txt = f"{dur:.0f}s" if dur else "durasi tidak diketahui"
        max_h = info.get("max_height")
        dl_h = info.get("download_height")
        qual_txt = ""
        if max_h:
            qual_txt = (f", kualitas max {max_h}p — download jadi "
                        f"{dl_h or max_h}p")
            if max_h < 1080:
                qual_txt += (f" (video ini mentok {max_h}p, "
                             "bukan salah tool)")
        log(f"Video: {title} ({dur_txt}{qual_txt})")
        self.after(0, lambda: self.yt_info.config(
            text=f"{title} — {dur_txt}{qual_txt}"))
        dl_dir = os.path.join(out_dir, "downloads")
        os.makedirs(dl_dir, exist_ok=True)
        template, expected = fu.download_target_path(dl_dir, title)
        last_pct = {"v": -1}

        def _progress(pct: float):
            log(f"  download: {pct:.0f}%")
            last_pct["v"] = pct

        ok, result = fu.download_youtube_video(
            ytdlp, url, template, expected, log=log, progress_cb=_progress)
        if not ok:
            raise RuntimeError(f"Download YouTube gagal:\n{result}")
        self.yt_downloaded.set(result)
        self._planned_key = None
        log(f"Download selesai (1080p terbaik): {result}")
        return result

    def _on_check_yt(self):
        if self.running:
            return
        url = self.yt_url.get().strip()
        problem = fu.youtube_url_problem(url)
        if problem:
            messagebox.showerror("URL YouTube", problem)
            return
        ytdlp = self._resolve_ytdlp()
        if not ytdlp:
            messagebox.showerror("yt-dlp", "yt-dlp tidak ketemu — jalankan "
                                 "setup-1-klik.bat lagi untuk download yt-dlp.exe.")
            return
        self.source_mode.set("youtube")
        self.running = True
        t = threading.Thread(target=self._check_yt_worker,
                             args=(url, ytdlp), daemon=True)
        t.start()

    def _check_yt_worker(self, url: str, ytdlp: str):
        try:
            self._log(f"Cek info video: {url}")
            info = fu.get_youtube_info(ytdlp, url)
            if info is None:
                raise RuntimeError("yt-dlp gagal membaca info video — mungkin "
                                   "video private / age-restricted / butuh "
                                   "login, atau YouTube memblokir IP ini.")
            dur = info["duration"]
            dur_txt = f"{dur:.0f}s" if dur else "durasi tidak diketahui"
            max_h = info.get("max_height")
            dl_h = info.get("download_height")
            qual_txt = ""
            if max_h:
                qual_txt = (f", kualitas max {max_h}p — download jadi "
                            f"{dl_h or max_h}p")
                if max_h < 1080:
                    qual_txt += (f" (video ini mentok {max_h}p, "
                                 "bukan salah tool)")
            self.after(0, lambda: self.yt_info.config(
                text=f"{info['title']} — {dur_txt}{qual_txt}"))
            self._log(f"Info: {info['title']} ({dur_txt}{qual_txt})")
        except Exception as e:
            self._log(f"❌ GAGAL cek info: {e}")
            self.after(0, lambda e=e: messagebox.showerror("Gagal", str(e)))
        finally:
            self.after(0, lambda: setattr(self, "running", False))

    def _on_download_yt(self):
        if self.running:
            return
        url = self.yt_url.get().strip()
        problem = fu.youtube_url_problem(url)
        if problem:
            messagebox.showerror("URL YouTube", problem)
            return
        out_dir = self.out_folder.get().strip()
        if not out_dir:
            messagebox.showerror("Output", "Isi folder output dulu.")
            return
        self.source_mode.set("youtube")
        self.running = True
        self.progress.start(10)
        t = threading.Thread(target=self._download_yt_worker,
                             args=(url, out_dir), daemon=True)
        t.start()

    def _download_yt_worker(self, url: str, out_dir: str):
        try:
            os.makedirs(out_dir, exist_ok=True)
            path = self._download_yt_sync(url, out_dir)
            self.after(0, self._refresh_video_info)
            self.after(0, lambda: messagebox.showinfo(
                "Download selesai", f"Video sudah di-download:\n{path}\n\n"
                "Tinggal klik POTONG buat mencincangnya."))
        except Exception as e:
            self._log(f"❌ GAGAL download: {e}")
            self.after(0, lambda e=e: messagebox.showerror("Gagal", str(e)))
        finally:
            self.after(0, self._finish_run)

    # ------------------------------------------------------------- probe cache
    def _spec(self, path: str) -> fu.MediaInfo:
        if path not in self._spec_cache:
            self._spec_cache[path] = fu.probe_specs(
                path, ffprobe=self.ffprobe_path.get())
        return self._spec_cache[path]

    def _refresh_video_info(self):
        p = self._effective_video_path()
        if not p:
            if self.source_mode.get() == "youtube":
                self.video_info.config(
                    text="Mode YouTube: tempel URL lalu klik Download dulu.")
            else:
                self.video_info.config(text="Belum ada video dipilih.")
            return
        info = self._spec(p)
        if info.duration <= 0 or info.width <= 0:
            self.video_info.config(
                text=f"GAGAL probe: {os.path.basename(p)} (durasi/resolusi tidak terbaca)")
            return
        fps_txt = f"{info.fps:.2f}" if info.fps > 0 else "?"
        self.video_info.config(
            text=f"{os.path.basename(p)} — {info.duration:.1f}s, "
                 f"{info.width}x{info.height}, {fps_txt} fps, {info.codec or '?'}")

    # ------------------------------------------------------------- GPU
    def _detect_gpu(self):
        ff = self.ffmpeg_path.get() or fu.find_ffmpeg()
        self._gpu_encoder = fu.detect_gpu_encoder(ff)
        self._refresh_gpu_label()

    def _refresh_gpu_label(self):
        names = {"h264_nvenc": "NVIDIA NVENC",
                 "h264_qsv": "Intel Quick Sync",
                 "h264_amf": "AMD AMF"}
        if not self.use_gpu_var.get():
            self.gpu_label.config(text="GPU: dimatikan — render pakai CPU (libx264)")
        elif self._gpu_encoder in names:
            self.gpu_label.config(
                text=f"GPU: {names[self._gpu_encoder]} — render pakai GPU")
        else:
            self.gpu_label.config(
                text="GPU: tidak terdeteksi — render pakai CPU (libx264)")

    # ------------------------------------------------------------- settings
    def _read_min_max(self):
        try:
            mn = float(self.min_dur.get())
            mx = float(self.max_dur.get())
        except ValueError:
            raise ValueError("Min/Max durasi harus angka.")
        if mn < 1:
            raise ValueError("Min durasi minimal 1 detik.")
        if mx < mn:
            raise ValueError("Max durasi harus >= Min durasi.")
        if mx > 300:
            raise ValueError("Max durasi maksimal 300 detik.")
        return mn, mx

    def _plan(self, total: float, mn: float, mx: float):
        """Plan (durations, effects, extras_list); reuse the preview plan
        when the settings key matches, so Preview and POTONG agree."""
        key = (self._effective_video_path(), mn, mx, self.intensity.get(),
               self.flip_var.get(), self.speed_var.get(), self.rotate_var.get())
        if self._planned_key == key and self._planned is not None:
            return self._planned
        durations = fu.plan_clips(total, mn, mx)
        effects = fu.assign_effects(len(durations))
        rng = random.Random()
        extras_list = [fu.roll_extra_effects(rng, self.flip_var.get(),
                                             self.speed_var.get(),
                                             self.rotate_var.get())
                       for _ in durations]
        self._planned_key = key
        self._planned = (durations, effects, extras_list)
        return self._planned

    def _on_preview(self):
        p = self._effective_video_path()
        if not p:
            if self.source_mode.get() == "youtube":
                messagebox.showinfo("Preview", "Mode YouTube: tempel URL lalu "
                                  "klik Download dulu (atau klik POTONG — "
                                  "download jalan otomatis).")
            else:
                messagebox.showinfo("Preview", "Pilih file video dulu.")
            return
        try:
            mn, mx = self._read_min_max()
        except ValueError as e:
            messagebox.showerror("Durasi", str(e))
            return
        info = self._spec(p)
        if info.duration <= 0 or info.width <= 0:
            messagebox.showerror("Video", "Durasi/resolusi video tidak terbaca (probe gagal).")
            return
        durations, effects, extras_list = self._plan(info.duration, mn, mx)
        # Force a fresh plan on next preview click (preview is a new roll).
        self._planned_key = None
        starts, t = [], 0.0
        for d in durations:
            starts.append(t)
            t += d
        extra_on = [n for n, v in (("flip", self.flip_var.get()),
                                   ("speed", self.speed_var.get()),
                                   ("rotate", self.rotate_var.get())) if v]
        lines = [f"Video {info.duration:.1f}s -> {len(durations)} klip "
                 f"(Min {mn:g}s / Max {mx:g}s, intensitas: {self.intensity.get()}):",
                 f"Efek tambahan: {', '.join(extra_on) if extra_on else 'mati semua (hasil = v1)'}"
                 f" — flip 50%/klip, speed 0.92-1.08x, rotate 0.5-2°."]
        for i, (s, d, e, ex) in enumerate(zip(starts, durations, effects, extras_list)):
            if i >= 15:
                lines.append(f"  … +{len(durations) - 15} klip lagi")
                break
            desc = fu.format_extra_effects(ex)
            extra_txt = f" + {desc}" if desc else ""
            lines.append(f"  {i+1}. {s:6.1f}s - {s + d:6.1f}s  ({d:.1f}s)  {fu.EFFECT_LABELS[e]}{extra_txt}")
        self.preview_label.config(text="\n".join(lines))
        self._log(f"Preview: {len(durations)} klip dari {info.duration:.1f}s "
                  f"(Min {mn:g}s / Max {mx:g}s, {self.intensity.get()})")

    # ------------------------------------------------------------- cut
    def _on_cancel(self):
        self._log("Batalkan ditekan — pekerjaan yang sedang jalan akan diselesaikan "
                  "di langkah aman berikutnya (v1: tidak mematikan ffmpeg paksa).")
        messagebox.showinfo("Batalkan", "v1: tunggu klip saat ini selesai, "
                            "atau tutup aplikasi. Potongan berikutnya tidak akan dimulai.")

    def _on_cut(self):
        if self.running:
            return
        p = self._effective_video_path()
        if not p:
            # Mode YouTube + URL ada tapi belum di-download: POTONG
            # download dulu otomatis di worker, baru cincang.
            if self.source_mode.get() == "youtube" and self.yt_url.get().strip():
                p = ""
            else:
                messagebox.showerror("Video", "Pilih file video dulu "
                                     "(atau tempel URL YouTube lalu Download).")
                return
        try:
            mn, mx = self._read_min_max()
        except ValueError as e:
            messagebox.showerror("Durasi", str(e))
            return
        out_dir = self.out_folder.get().strip()
        if not out_dir:
            messagebox.showerror("Output", "Isi folder output dulu.")
            return
        self.running = True
        self.btn_cut.config(state="disabled")
        self.progress.start(10)
        t = threading.Thread(target=self._cut_worker,
                             args=(p, mn, mx, out_dir), daemon=True)
        t.start()

    def _cut_worker(self, video_path: str, mn: float, mx: float, out_dir: str):
        log = self._log
        try:
            os.makedirs(out_dir, exist_ok=True)
            if not video_path:
                # Mode YouTube, belum di-download: download dulu, baru cincang.
                log("Mode YouTube: download dulu sebelum potong…")
                video_path = self._download_yt_sync(
                    self.yt_url.get().strip(), out_dir)
            ff = self.ffmpeg_path.get() or fu.find_ffmpeg()
            fp = self.ffprobe_path.get() or fu.find_ffprobe()
            info = fu.probe_specs(video_path, ffprobe=fp)
            if info.duration <= 0 or info.width <= 0:
                raise RuntimeError("Durasi/resolusi video tidak terbaca (probe gagal).")
            self._spec_cache[video_path] = info
            encoder = (fu.detect_gpu_encoder(ff)
                       if self.use_gpu_var.get() else None)
            log(f"Video: {os.path.basename(video_path)} — {info.duration:.1f}s, "
                f"{info.width}x{info.height}, {info.fps:.2f} fps")
            log(f"GPU: {encoder or 'CPU libx264'}"
                f" | Intensitas: {self.intensity.get()}"
                f" | Efek tambahan: flip={'ON' if self.flip_var.get() else 'OFF'}, "
                f"speed={'ON' if self.speed_var.get() else 'OFF'}, "
                f"rotate={'ON' if self.rotate_var.get() else 'OFF'}")
            durations, effects, extras_list = self._plan(info.duration, mn, mx)
            self._planned_key = None  # next run re-rolls
            fps = info.fps if info.fps > 0 else 30.0
            starts, t = [], 0.0
            for d in durations:
                starts.append(t)
                t += d
            rng = random.Random()
            ok_count, fail_count = 0, 0
            for i, (start, dur, eff, ex) in enumerate(
                    zip(starts, durations, effects, extras_list), 1):
                out_path = fu.unique_random_output_path(out_dir, rng=rng)
                name = os.path.basename(out_path)
                desc = fu.format_extra_effects(ex)
                extra_txt = f" + {desc}" if desc else ""
                exp_dur = dur / ex["speed"] if ex.get("speed") else dur
                log(f"[{i}/{len(durations)}] {name}  {dur:.1f}s -> {exp_dur:.1f}s  "
                    f"{fu.EFFECT_LABELS[eff]}{extra_txt}  (mulai {start:.1f}s)")
                ok = fu.render_clip(video_path, start, dur, out_path, eff,
                                    self.intensity.get(),
                                    info.width, info.height, fps,
                                    encoder=encoder, log=log, ffmpeg=ff,
                                    extras=ex)
                if ok:
                    ok_count += 1
                else:
                    fail_count += 1
                    log(f"  GAGAL klip {i}: {name}")
            if fail_count:
                log(f"SELESAI (dengan {fail_count} klip gagal): "
                    f"{ok_count} klip di {out_dir}")
                self.after(0, lambda: messagebox.showwarning(
                    "Selesai (sebagian gagal)",
                    f"{ok_count} klip berhasil, {fail_count} gagal.\nFolder: {out_dir}"))
            else:
                log(f"✅ SELESAI: {ok_count} klip di {out_dir}")
                self.after(0, lambda: messagebox.showinfo(
                    "Selesai", f"{ok_count} klip berhasil dibuat:\n{out_dir}"))
        except Exception as e:
            log(f"❌ GAGAL: {e}")
            self.after(0, lambda e=e: messagebox.showerror("Gagal", str(e)))
        finally:
            self.after(0, self._finish_run)

    def _finish_run(self):
        self.running = False
        self.btn_cut.config(state="normal")
        self.progress.stop()
        self._refresh_video_info()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
