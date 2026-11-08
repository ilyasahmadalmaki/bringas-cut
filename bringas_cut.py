"""
Bringas Cut — bringas_cut.py
Windows desktop tool (Python 3.10+ Tkinter, stdlib only).
Cincang 1 video jadi banyak klip, audio dibuang total, tiap klip
dikasih 1 efek random yang beda dari klip lain, nama file output acak.

Jalankan:  python bringas_cut.py
           (atau double-click run.bat di Windows)
ffmpeg.exe + ffprobe.exe harus ada di folder aplikasi atau di PATH
(gyan.dev builds).
"""
from __future__ import annotations

import os
import queue
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bringas Cut — HYDRA TEAM BRINGAS")
        self.geometry("980x820")
        self.configure(bg=BG)
        self.log_q: queue.Queue = queue.Queue()
        self.running = False
        self.ffmpeg_path = tk.StringVar(value=fu.find_ffmpeg())
        self.ffprobe_path = tk.StringVar(value=fu.find_ffprobe())

        # State
        self.video_file = tk.StringVar()
        self.min_dur = tk.StringVar(value="3")
        self.max_dur = tk.StringVar(value="8")
        self.intensity = tk.StringVar(value=fu.DEFAULT_INTENSITY)
        self.out_folder = tk.StringVar(value=str(Path.home() / "Videos" / "BringasCut"))
        self.use_gpu_var = tk.BooleanVar(value=True)
        self._gpu_encoder = None
        # Probe cache (per session): probe each path once and reuse it.
        self._spec_cache: dict[str, fu.MediaInfo] = {}
        # Preview plan, reused by POTONG when settings did not change.
        self._planned_key = None
        self._planned = None  # (durations, effects)

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

        # ---- Video ----
        vf = ttk.LabelFrame(root, text="1 — Video (1 file, lokal saja)", padding=8)
        vf.pack(fill="x", pady=4)
        row = ttk.Frame(vf); row.pack(fill="x", pady=2)
        ttk.Entry(row, textvariable=self.video_file, width=70).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse…", command=self._pick_video_file).pack(side="left", padx=4)
        self.video_info = tk.Label(vf, text="Belum ada video dipilih.",
                                   bg=PANEL, fg=MUTED, anchor="w")
        self.video_info.pack(fill="x", pady=2)
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

        # ---- Preview + Output ----
        pf = ttk.LabelFrame(root, text="3 — Preview & Output", padding=8)
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
        sf = ttk.LabelFrame(root, text="Pengaturan ffmpeg", padding=8)
        sf.pack(fill="x", pady=4)
        for label, var in (("ffmpeg:", self.ffmpeg_path), ("ffprobe:", self.ffprobe_path)):
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
        self._log("Bringas Cut siap. Pilih 1 video, atur Min/Max + intensitas, lalu POTONG.")
        self._log("Catatan jujur: efek acak bikin klip makin beda dari aslinya, tapi TIDAK ADA jaminan 100% lolos Content ID / review reused-content YouTube.")
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
            self._planned_key = None
            self._refresh_video_info()

    def _pick_out_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.out_folder.set(p)

    # ------------------------------------------------------------- probe cache
    def _spec(self, path: str) -> fu.MediaInfo:
        if path not in self._spec_cache:
            self._spec_cache[path] = fu.probe_specs(
                path, ffprobe=self.ffprobe_path.get())
        return self._spec_cache[path]

    def _refresh_video_info(self):
        p = self.video_file.get()
        if not p:
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
        """Plan (durations, effects); reuse the preview plan when the
        settings key matches, so Preview and POTONG agree."""
        key = (self.video_file.get(), mn, mx, self.intensity.get())
        if self._planned_key == key and self._planned is not None:
            return self._planned
        durations = fu.plan_clips(total, mn, mx)
        effects = fu.assign_effects(len(durations))
        self._planned_key = key
        self._planned = (durations, effects)
        return self._planned

    def _on_preview(self):
        p = self.video_file.get()
        if not p:
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
        durations, effects = self._plan(info.duration, mn, mx)
        # Force a fresh plan on next preview click (preview is a new roll).
        self._planned_key = None
        starts, t = [], 0.0
        for d in durations:
            starts.append(t)
            t += d
        lines = [f"Video {info.duration:.1f}s -> {len(durations)} klip "
                 f"(Min {mn:g}s / Max {mx:g}s, intensitas: {self.intensity.get()}):"]
        for i, (s, d, e) in enumerate(zip(starts, durations, effects)):
            if i >= 15:
                lines.append(f"  … +{len(durations) - 15} klip lagi")
                break
            lines.append(f"  {i+1}. {s:6.1f}s - {s + d:6.1f}s  ({d:.1f}s)  {fu.EFFECT_LABELS[e]}")
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
        p = self.video_file.get()
        if not p or not os.path.isfile(p):
            messagebox.showerror("Video", "Pilih file video dulu.")
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
                f" | Intensitas: {self.intensity.get()}")
            durations, effects = self._plan(info.duration, mn, mx)
            self._planned_key = None  # next run re-rolls
            fps = info.fps if info.fps > 0 else 30.0
            starts, t = [], 0.0
            for d in durations:
                starts.append(t)
                t += d
            rng = random.Random()
            ok_count, fail_count = 0, 0
            for i, (start, dur, eff) in enumerate(zip(starts, durations, effects), 1):
                out_path = fu.unique_random_output_path(out_dir, rng=rng)
                name = os.path.basename(out_path)
                log(f"[{i}/{len(durations)}] {name}  {dur:.1f}s  "
                    f"{fu.EFFECT_LABELS[eff]}  (mulai {start:.1f}s)")
                ok = fu.render_clip(video_path, start, dur, out_path, eff,
                                    self.intensity.get(),
                                    info.width, info.height, fps,
                                    encoder=encoder, log=log, ffmpeg=ff)
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
