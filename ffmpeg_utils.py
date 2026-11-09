"""
Bringas Cut — ffmpeg_utils.py
Core logic (no GUI) for Bringas Cut.

Locked spec (2026-11-08, user discussion):
- Windows app, Python Tkinter stdlib-only + ffmpeg.
- Input: ONE local video file (no YouTube download).
- Chop it into many clips. Audio from the original is REMOVED
  totally (-an) on every clip.
- Clip duration CUSTOM: user sets Min and Max seconds
  (default Min 3, Max 8). Each clip duration is random uniform
  in [Min, Max].
- Remainder rule (user did not answer; this is the documented
  decision): if the tail remainder is < Min, merge it into the
  last clip (extend the last clip) — never emit a tiny <Min clip,
  except when the whole video itself is shorter than Min
  (then one clip = whole video).
- Effect intensity: 3 options — "Lembut banget", "Lembut"
  (default), "Guncang". Scales zoom/shake amplitude.
- Effects: each clip gets ONE random effect, DIFFERENT from
  other clips — shuffled 8-effect pool, cycled: use all 8 before
  repeating, reshuffle each cycle, no two adjacent clips share
  the same effect (cycle boundary fixed by swapping).
  Pool: zoom_in, zoom_out, zoom_breathe, pan_left, pan_right,
  pan_up, shake_soft, zoom_shake. No mirror/flip.
- Output filenames RANDOM, not sequential: random 10-char
  [a-z0-9] + .mp4, regenerated on collision. No klip_01/klip_02.
- Quality HIGH: keep original width/height/fps, re-encode per
  clip. CPU libx264 CRF 18 preset veryfast; GPU if detected:
  NVENC p4+CQ19 / QSV medium+ICQ19 / AMF balanced+CQP19.
- No output verification ("sikat aja"): ffmpeg exit 0 + file
  exists = success.
- No black cmd window on Windows: CREATE_NO_WINDOW for all
  ffmpeg/ffprobe subprocesses.
- v1.1 (2026-11-09): 3 efek tambahan OPSIONAL per klip, di atas efek
  utama — Mirror flip (50% per klip), Speed acak 0.92-1.08x (durasi
  output = rencana/speed), Rotate miring acak 0.5-2 derajat (overscale
  dulu biar tidak ada sudut hitam). Semua default ON, bisa dimatikan
  satu-satu di GUI. Kalau ketiganya mati, hasil identik dengan v1.
- v1.2 (2026-11-09): sumber video 2 opsi — File lokal (perilaku lama)
  atau Download dari YouTube via yt-dlp. Kualitas download: 1080p
  TERBAIK (format terbaik dengan tinggi <= 1080, fallback ke yang
  terbaik di bawahnya kalau sumber max 720p; hasil akhir WAJIB .mp4,
  tidak pernah di atas 1080p, tidak pernah .webm/.mkv). yt-dlp dicari
  di sebelah aplikasi dulu, lalu di PATH; kalau tidak ketemu, GUI
  menyuruh jalankan setup-1-klik.bat lagi (yt-dlp TIDAK di-download
  diam-diam saat render — hanya lewat setup). Tanpa cookies/login:
  video yang butuh login / age-restricted / private akan gagal dengan
  pesan error yang jelas. Satu video saja, BUKAN playlist.
  Peringatan ToS ada di GUI + README: download hanya untuk video
  milik sendiri / yang kamu punya hak pakainya.
- v1.3 (2026-11-09): tombol Cek Info juga menampilkan kualitas MAX video
  (dari daftar format yt-dlp -J) + kualitas yang bakal di-download (terbaik
  <= 1080p), supaya ketahuan sebelum download kalau videonya
  memang mentok rendah (mis. 'Me at the zoo' cuma 240p) — bukan
  salah tool. Fallback ke judul+durasi lama kalau JSON gagal.
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse, parse_qs

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".ts"}

LogFn = Callable[[str], None]


def _noop_log(msg: str) -> None:
    pass


# --------------------------------------------------------------------------
# ffmpeg / ffprobe discovery
# --------------------------------------------------------------------------

def find_ffmpeg(explicit: Optional[str] = None) -> str:
    """Return ffmpeg executable path. App folder first, then PATH."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    here = Path(__file__).resolve().parent
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidates.append(str(here / name))
    candidates.append("ffmpeg")
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
        if os.path.isfile(c):
            return c
    return "ffmpeg"


def find_ffprobe(explicit: Optional[str] = None) -> str:
    candidates = []
    if explicit:
        candidates.append(explicit)
    here = Path(__file__).resolve().parent
    for name in ("ffprobe.exe", "ffprobe"):
        candidates.append(str(here / name))
    candidates.append("ffprobe")
    for c in candidates:
        p = shutil.which(c)
        if p:
            return p
        if os.path.isfile(c):
            return c
    return "ffprobe"


def _no_window_kwargs() -> dict:
    """Windows: hide the console window for ffmpeg/ffprobe children."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def _run(cmd: List[str], log: LogFn = _noop_log) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **_no_window_kwargs())


# --------------------------------------------------------------------------
# Probing
# --------------------------------------------------------------------------

@dataclass
class MediaInfo:
    path: str
    duration: float = 0.0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = ""


def _to_float(v) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _fps(fr) -> float:
    try:
        num, den = str(fr).split("/")
        return float(num) / float(den) if float(den) else 0.0
    except Exception:
        return 0.0


def _duration_from_probe(data: dict) -> float:
    """Best-effort duration from one ffprobe JSON dump.

    Fallback chain (same as Bringas Render PC):
    1. format duration
    2. any stream duration (video first, then the rest)
    3. video frames / fps
    """
    dur = _to_float((data.get("format") or {}).get("duration"))
    if dur > 0:
        return dur
    streams = data.get("streams") or []
    for s in streams:
        if s.get("codec_type") == "video":
            d = _to_float(s.get("duration"))
            if d > 0:
                return d
    for s in streams:
        d = _to_float(s.get("duration"))
        if d > 0:
            return d
    for s in streams:
        if s.get("codec_type") == "video":
            frames = _to_float(s.get("nb_frames"))
            fps = _fps(s.get("avg_frame_rate") or s.get("r_frame_rate"))
            if frames > 0 and fps > 0:
                return frames / fps
    return 0.0


def probe_duration(path: str, ffprobe: Optional[str] = None) -> float:
    """Duration in seconds via ffprobe, 0.0 on failure."""
    fp = find_ffprobe(ffprobe)
    cmd = [fp, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           **_no_window_kwargs())
        data = json.loads(r.stdout or "{}")
        return _duration_from_probe(data)
    except Exception:
        return 0.0


def probe_specs(path: str, ffprobe: Optional[str] = None) -> MediaInfo:
    """Width/height/fps/codec + duration via ffprobe."""
    info = MediaInfo(path=path)
    fp = find_ffprobe(ffprobe)
    cmd = [fp, "-v", "quiet", "-print_format", "json",
           "-show_format", "-show_streams", path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60,
                           **_no_window_kwargs())
        data = json.loads(r.stdout or "{}")
        info.duration = _duration_from_probe(data)
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and not info.codec:
                info.codec = s.get("codec_name", "")
                info.width = int(s.get("width", 0) or 0)
                info.height = int(s.get("height", 0) or 0)
                fr = s.get("r_frame_rate") or s.get("avg_frame_rate") or "0/1"
                info.fps = _fps(fr)
    except Exception:
        pass
    return info


# --------------------------------------------------------------------------
# GPU detection (NVENC / Quick Sync / AMF) — same pattern as Bringas
# --------------------------------------------------------------------------

_GPU_ENCODERS = ("h264_nvenc", "h264_qsv", "h264_amf")
_GPU_CACHE: dict = {}


def parse_encoders_list(text: str) -> List[str]:
    """Hardware H.264 encoders in `ffmpeg -encoders` output, in
    priority order (NVENC > QSV > AMF). Pure function, easy to test."""
    found = set()
    for line in (text or "").splitlines():
        for tok in line.split():
            if tok in _GPU_ENCODERS:
                found.add(tok)
    return [name for name in _GPU_ENCODERS if name in found]


def parse_encoders_output(text: str) -> Optional[str]:
    """Best hardware H.264 encoder found in `ffmpeg -encoders` output,
    or None."""
    lst = parse_encoders_list(text)
    return lst[0] if lst else None


def _encoder_probe_ok(ffmpeg: str, encoder: str) -> bool:
    """True if `encoder` actually works on this machine.

    `ffmpeg -encoders` only lists compiled-in encoders — NVENC is
    listed even without an NVIDIA GPU, so a tiny 1-frame encode is
    the real test (fails fast without the driver/hardware).
    """
    try:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-y",
             "-f", "lavfi", "-i", "nullsrc=s=64x64:d=0.1",
             "-frames:v", "1", "-c:v", encoder, "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
            **_no_window_kwargs())
        return r.returncode == 0
    except Exception:
        return False


def detect_gpu_encoder(ffmpeg: Optional[str] = None) -> Optional[str]:
    """Detect the best hardware H.264 encoder this ffmpeg supports
    AND that actually works on this machine. Cached per ffmpeg path.
    Never raises — any failure means CPU fallback."""
    ff = find_ffmpeg(ffmpeg)
    if ff in _GPU_CACHE:
        return _GPU_CACHE[ff]
    result: Optional[str] = None
    try:
        r = subprocess.run([ff, "-hide_banner", "-encoders"],
                           capture_output=True, text=True, timeout=30,
                           **_no_window_kwargs())
        for name in parse_encoders_list(r.stdout or ""):
            if _encoder_probe_ok(ff, name):
                result = name
                break
    except Exception:
        result = None
    _GPU_CACHE[ff] = result
    return result


def video_encoder_args(encoder: Optional[str] = None) -> List[str]:
    """ffmpeg video-encode flags for the chosen encoder.

    None (or unknown) -> CPU libx264 crf 18 preset veryfast.
    GPU encoders use a comparable constant-quality setting:
    NVENC p4 + CQ 19, Quick Sync medium + ICQ 19, AMF balanced + CQP 19.
    """
    if encoder == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "19",
                "-pix_fmt", "yuv420p"]
    if encoder == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "medium",
                "-global_quality", "19", "-pix_fmt", "yuv420p"]
    if encoder == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp",
                "-qp_i", "19", "-qp_p", "19", "-qp_b", "19",
                "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-pix_fmt", "yuv420p"]


# --------------------------------------------------------------------------
# YouTube download via yt-dlp (v1.2)
# --------------------------------------------------------------------------

# Quality: BEST 1080p. The format string picks the best video with
# height <= 1080 (a 4K source gives its 1080p stream, never 4K; a
# 720p-max source gives 720p — the best that exists at/below 1080p)
# + best audio, merged to .mp4. Never above 1080p, never .webm/.mkv.
YTDLP_FORMAT = (
    "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/"
    "bv*[height<=1080]+ba/"
    "b[height<=1080][ext=mp4]/b[height<=1080]"
)
# Player clients, in order: android first — it still works on IPs that
# get bot-checked/429 on the web client (verified 2026-11-09 from this
# VM: web client 429s on every request, android returns metadata and
# downloads fine); web as fallback for full format lists on normal
# residential IPs. NOTE: on a bot-checked IP the android client may be
# SABR-limited and only offer lower heights (e.g. 360p for an old
# video) — the <=1080 cap still holds, it is just the best AVAILABLE
# on that network. On a normal PC the web client should offer 1080p.
YTDLP_EXTRACTOR_ARGS = "youtube:player_client=android,web"

_YT_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "www.music.youtube.com",
    "youtube-nocookie.com", "www.youtube-nocookie.com",
    "youtu.be", "www.youtu.be",
}
_YT_VIDEO_PATHS = ("/watch", "/shorts/", "/embed/", "/live/", "/v/")


def is_youtube_url(url: str) -> bool:
    """True for a single YouTube video URL.

    Accepts youtube.com/watch, /shorts/, /embed/, /live/, /v/,
    music.youtube.com, and youtu.be/<id> — with or without scheme.
    Rejects other domains, bare youtube.com, youtu.be with no id,
    and /playlist URLs (v1.2 is one video, not a playlist).
    """
    if not url or not str(url).strip():
        return False
    u = str(url).strip()
    if "://" not in u:
        u = "https://" + u
    try:
        p = urlparse(u)
    except Exception:
        return False
    host = (p.netloc or "").lower().split(":")[0]
    if host not in _YT_HOSTS:
        return False
    path = p.path or ""
    if host in ("youtu.be", "www.youtu.be"):
        return len(path.strip("/")) > 0
    if path == "/watch":
        return bool(parse_qs(p.query).get("v"))
    if path == "/playlist":
        return False
    return any(path.startswith(prefix) for prefix in _YT_VIDEO_PATHS)


def youtube_url_problem(url: str) -> Optional[str]:
    """Human-readable reason the URL cannot be used, or None if OK.

    Playlist-only URLs (list= without v=) are rejected here too:
    v1.2 downloads ONE video, not a playlist.
    """
    if not url or not str(url).strip():
        return "Tempel URL video YouTube dulu."
    u = str(url).strip()
    if "://" not in u:
        u = "https://" + u
    # Playlist-only ditolak dengan pesan khusus dulu (sebelum cek domain/
    # bentuk umum) supaya user tahu persis salahnya di mana.
    try:
        p = urlparse(u)
        q = parse_qs(p.query)
    except Exception:
        p, q = None, {}
    if (p is not None and p.path == "/playlist") or ("list" in q and "v" not in q):
        return ("URL playlist tidak didukung di v1.2 — tempel URL 1 video "
                "(youtube.com/watch?v=...) saja.")
    if not is_youtube_url(url):
        return ("URL bukan video YouTube yang didukung — pakai link "
                "youtube.com/watch, youtube.com/shorts/, atau youtu.be/.")
    return None


def find_yt_dlp(explicit: Optional[str] = None) -> Optional[str]:
    """Return yt-dlp executable path, or None when not found.

    Order: explicit path (if it exists) -> yt-dlp.exe / yt-dlp next to
    this script (where setup-1-klik.bat puts it) -> PATH.
    Returning None (instead of a blind "yt-dlp" fallback) lets the GUI
    show a clear "jalankan setup-1-klik.bat lagi" error.
    """
    if explicit and os.path.isfile(explicit):
        return explicit
    here = Path(__file__).resolve().parent
    for name in ("yt-dlp.exe", "yt-dlp"):
        cand = str(here / name)
        if os.path.isfile(cand):
            return cand
    for name in ("yt-dlp.exe", "yt-dlp"):
        p = shutil.which(name)
        if p:
            return p
    return None


def build_ytdlp_command(yt_dlp: str, url: str,
                        output_template: str) -> List[str]:
    """yt-dlp command for one video at best-1080p, output to .mp4.

    `output_template` must contain %(ext)s (e.g. ".../Judul.%(ext)s").
    --no-playlist: a playlist URL with v= downloads just that video.
    --newline: one progress line per update, parseable by
    parse_ytdlp_progress. The extractor args put the android client
    first (bot-check resistant) with web as fallback.
    """
    return [yt_dlp, "--no-playlist",
            "--extractor-args", YTDLP_EXTRACTOR_ARGS,
            "-f", YTDLP_FORMAT,
            "--merge-output-format", "mp4",
            "--newline",
            "-o", output_template, url]


_PROGRESS_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")


def parse_ytdlp_progress(line: str) -> Optional[float]:
    """Parse a yt-dlp progress line -> percent float, or None.

    "[download]  45.2% of  12.34MiB at  1.20MiB/s ETA 00:05" -> 45.2
    "[download] 100% of ..." -> 100.0. Anything else -> None.
    """
    if not line:
        return None
    m = _PROGRESS_RE.search(line)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parse_duration_text(text: str) -> Optional[float]:
    """Parse yt-dlp --get-duration output: seconds, MM:SS, or HH:MM:SS."""
    s = (text or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    parts = s.split(":")
    try:
        nums = [float(x) for x in parts]
    except ValueError:
        return None
    total = 0.0
    for n in nums:
        total = total * 60.0 + n
    return total if total > 0 else None


def _heights_from_formats(formats) -> Tuple[Optional[int], Optional[int]]:
    """(max_height, download_height) dari daftar format yt-dlp.

    max_height = tinggi terbesar dari semua format VIDEO (audio-only
    diabaikan — vcodec none). download_height = tinggi terbesar yang
    <= 1080, yaitu yang bakal diambil format string YTDLP_FORMAT
    (4K -> 1080, sumber 720p -> 720, 'Me at the zoo' -> 240).
    (None, None) kalau tidak ada format video bertinggi.
    """
    heights = []
    for f in (formats or []):
        if not isinstance(f, dict):
            continue
        if (f.get("vcodec") or "none") in ("none", None):
            continue
        try:
            h = int(f.get("height") or 0)
        except (TypeError, ValueError):
            continue
        if h > 0:
            heights.append(h)
    if not heights:
        return None, None
    under = [h for h in heights if h <= 1080]
    return max(heights), (max(under) if under else max(heights))


def get_youtube_info(yt_dlp: str, url: str,
                     timeout: int = 60) -> Optional[dict]:
    """Fetch a video's title + duration + max quality via yt-dlp (no download).

    Returns {"title": str, "duration": float|None,
             "max_height": int|None, "download_height": int|None}
    or None on failure (private / age-restricted / login-required /
    network error). Never raises.

    max_height = kualitas tertinggi yang dimiliki video itu (dari
    daftar format yt-dlp); download_height = yang bakal di-download
    format string kita (terbaik <= 1080p). Kalau video aslinya cuma
    240p (mis. 'Me at the zoo', upload 2005), keduanya 240 — jadi
    user langsung tahu videonya yang mentok, bukan tool-nya.

    Cara baca: yt-dlp -J (JSON lengkap) dulu; kalau JSON gagal
    dibaca, fallback ke --get-title/--get-duration lama (judul +
    durasi tetap dapat, tinggi jadi None).
    """
    cmd = [yt_dlp, "--no-playlist",
           "--extractor-args", YTDLP_EXTRACTOR_ARGS,
           "-J", "--no-download", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout, **_no_window_kwargs())
    except Exception:
        r = None
    if r is not None and r.returncode == 0 and (r.stdout or "").strip():
        try:
            data = json.loads(r.stdout)
        except Exception:
            data = None
        if isinstance(data, dict) and data.get("title"):
            max_h, dl_h = _heights_from_formats(data.get("formats"))
            dur = data.get("duration")
            try:
                dur = float(dur) if dur is not None else None
            except (TypeError, ValueError):
                dur = None
            return {"title": str(data["title"]), "duration": dur,
                    "max_height": max_h, "download_height": dl_h}
    # Fallback lama: judul + durasi saja, tanpa info kualitas.
    cmd = [yt_dlp, "--no-playlist",
           "--extractor-args", YTDLP_EXTRACTOR_ARGS,
           "--get-title", "--get-duration", "--no-download", url]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout, **_no_window_kwargs())
    except Exception:
        return None
    if r.returncode != 0:
        return None
    lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    if not lines:
        return None
    title = lines[0]
    duration = _parse_duration_text(lines[1]) if len(lines) > 1 else None
    return {"title": title, "duration": duration,
            "max_height": None, "download_height": None}


def sanitize_filename(name: str) -> str:
    """Make a string safe as a Windows filename stem (same rules as
    Bringas Render PC): illegal chars -> _, whitespace runs -> _,
    max 120 chars, empty -> 'video'."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name))
    name = re.sub(r"\s+", "_", name.strip())
    return name[:120] or "video"


def unique_numbered_path(path: str) -> str:
    """Never overwrite: if `path` exists, append ' (1)', ' (2)', ...
    before the extension (Windows-Explorer style). A name that already
    ends with ' (N)' counts up from N."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    m = re.match(r"^(.*) \((\d+)\)$", base)
    n = int(m.group(2)) if m else 0
    if m:
        base = m.group(1)
    while True:
        n += 1
        cand = f"{base} ({n}){ext}"
        if not os.path.exists(cand):
            return cand


def download_target_path(folder: str, title: str) -> Tuple[str, str]:
    """(output_template, expected_mp4_path) for a downloaded video.

    Name = sanitized video title + .mp4, inside `folder`, numbered
    (1)/(2)... on collision. The template keeps %(ext)s so yt-dlp
    substitutes the real extension (mp4, enforced by the merge
    format), and the expected path is deterministic for the caller.
    """
    stem = os.path.join(folder, sanitize_filename(title))
    expected = unique_numbered_path(stem + ".mp4")
    template = os.path.splitext(expected)[0] + ".%(ext)s"
    return template, expected


def download_youtube_video(yt_dlp: str, url: str, output_template: str,
                           expected_path: str, log: LogFn = _noop_log,
                           progress_cb: Optional[Callable[[float], None]] = None
                           ) -> Tuple[bool, Optional[str]]:
    """Download one YouTube video with yt-dlp (streaming, for progress).

    Runs yt-dlp with stdout+stderr merged so progress lines can be
    parsed live; progress_cb is called when the percent moves >= 5
    points or hits 100 (throttled — yt-dlp emits many lines per
    second). Returns (True, expected_path) on success — yt-dlp exit 0
    AND the .mp4 file exists and is non-empty — or (False, error_tail)
    where error_tail is the last few non-empty output lines.
    Never raises.
    """
    cmd = build_ytdlp_command(yt_dlp, url, output_template)
    log("$ " + " ".join(cmd))
    tail: List[str] = []
    last_reported = -100.0
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8",
                                errors="replace",
                                **_no_window_kwargs())
    except Exception as e:
        return False, f"Gagal menjalankan yt-dlp: {e}"
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            tail.append(line)
            if len(tail) > 8:
                tail.pop(0)
            pct = parse_ytdlp_progress(line)
            if pct is not None and progress_cb is not None:
                if pct >= last_reported + 5.0 or pct >= 100.0:
                    last_reported = pct
                    try:
                        progress_cb(pct)
                    except Exception:
                        pass
        proc.wait()
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        return False, f"Download terputus: {e}"
    if proc.returncode != 0:
        return False, "\n".join(tail[-5:]) or f"yt-dlp exit {proc.returncode}"
    if os.path.isfile(expected_path) and os.path.getsize(expected_path) > 0:
        return True, expected_path
    # Fallback: yt-dlp sometimes writes a different extension despite
    # --merge-output-format (e.g. single-format source). Prefer .mp4.
    stem = os.path.splitext(expected_path)[0]
    for ext in (".mp4", ".mkv", ".webm", ".m4v"):
        cand = stem + ext
        if os.path.isfile(cand) and os.path.getsize(cand) > 0:
            return True, cand
    return False, "yt-dlp selesai tapi file output tidak ketemu."


# --------------------------------------------------------------------------
# Effects
# --------------------------------------------------------------------------

EFFECTS = ("zoom_in", "zoom_out", "zoom_breathe", "pan_left", "pan_right",
           "pan_up", "shake_soft", "zoom_shake")

# Intensity presets: zoom_max (relative zoom at peak), shake_amp (px at
# 1080p width 1920, scaled proportionally for other widths),
# shake_freq (Hz). "Lembut banget" is the gentlest, "Guncang" the strongest.
INTENSITY_PRESETS = {
    "Lembut banget": {"zoom": 1.06, "shake": 5.0, "freq": 1.2},
    "Lembut": {"zoom": 1.12, "shake": 10.0, "freq": 1.6},
    "Guncang": {"zoom": 1.20, "shake": 22.0, "freq": 2.8},
}
INTENSITIES = tuple(INTENSITY_PRESETS.keys())
DEFAULT_INTENSITY = "Lembut"

EFFECT_LABELS = {
    "zoom_in": "Zoom In",
    "zoom_out": "Zoom Out",
    "zoom_breathe": "Zoom Napas (masuk-keluar)",
    "pan_left": "Pan Kiri",
    "pan_right": "Pan Kanan",
    "pan_up": "Pan Atas",
    "shake_soft": "Guncang Lembut",
    "zoom_shake": "Zoom + Guncang",
}


def _even(n: float) -> int:
    """Round to nearest even int (yuv420p needs even dimensions)."""
    return max(2, int(round(n / 2.0)) * 2)


def build_effect_filter(width: int, height: int, effect: str,
                        intensity: str = DEFAULT_INTENSITY,
                        duration: float = 5.0, fps: float = 30.0) -> str:
    """ffmpeg -vf string for one effect on one clip.

    Uses the `zoompan` filter — the canonical ffmpeg way to do smooth
    zoom. (The first attempt used scale+crop with a time-varying crop
    window, but crop's w/h are evaluated ONCE at filter init, so `t`
    in w/h fails with "Error when evaluating the expression" — zoom
    via crop is impossible; pan/shake via crop x/y worked, zoom did
    not. zoompan evaluates z/x/y per output frame, so it does all 8.)

    Each clip is rendered in its own ffmpeg call, so zoompan's output
    frame counter `on` starts at 0 for the clip. Total frames
    N = round(duration * fps); zoom/pan progress is on/N, shake uses
    on/fps as time in seconds. All offsets are clamped to the
    available margin (min(amp, margin/2*0.9) or a fraction of the
    margin), so the zoom window can never leave the frame.
    z/x/y expressions are single-quoted inside the filter string so
    commas inside min(...) survive the filter parser.
    """
    if effect not in EFFECTS:
        raise ValueError(f"efek tidak dikenal: {effect}")
    preset = INTENSITY_PRESETS.get(intensity, INTENSITY_PRESETS[DEFAULT_INTENSITY])
    zoom_max = float(preset["zoom"])
    shake_amp = float(preset["shake"])
    freq = float(preset["freq"])
    dur = max(0.1, float(duration))
    fps_i = max(1, int(round(fps))) if fps and fps > 0 else 30
    n_frames = max(1, int(round(dur * fps_i)))
    w = _even(width)
    h = _even(height)
    # Shake amplitude in input-frame pixels: preset px at 1920 wide,
    # scaled proportionally to this width.
    amp = shake_amp * (w / 1920.0)
    z = f"{zoom_max:.4f}"
    n = str(n_frames)
    f = f"{freq:.2f}"
    # Zoom factor over time, per effect. `on` = output frame counter.
    if effect == "zoom_in":
        zt = f"(1+({z}-1)*on/{n})"
    elif effect == "zoom_out":
        zt = f"({z}-({z}-1)*on/{n})"
    elif effect == "zoom_breathe":
        zt = f"(1+({z}-1)*(0.5-0.5*cos(2*PI*on/{n})))"
    elif effect == "zoom_shake":
        zt = f"(1+({z}-1)*on/{n})"
    else:
        # Pan / shake: hold a mid zoom so there is margin to move.
        z_mid = 1.0 + (zoom_max - 1.0) * 0.5
        zt = f"{z_mid:.4f}"

    # Centred zoom window: x/y of the top-left corner.
    cx = "(iw-iw/zoom)/2"
    cy = "(ih-ih/zoom)/2"
    # Shake offsets (same shape for shake_soft and zoom_shake).
    shake_x = (f"{cx}+sin(2*PI*{f}*on/{fps_i})*"
               f"min({amp:.1f},(iw-iw/zoom)/2*0.9)")
    shake_y = (f"{cy}+cos(2*PI*{f}*0.83*on/{fps_i})*"
               f"min({amp * 0.7:.1f},(ih-ih/zoom)/2*0.9)")

    if effect == "pan_left":
        x_expr = f"{cx}+(iw-iw/zoom)/2*0.85*(2*on/{n}-1)"
        y_expr = cy
    elif effect == "pan_right":
        x_expr = f"{cx}-(iw-iw/zoom)/2*0.85*(2*on/{n}-1)"
        y_expr = cy
    elif effect == "pan_up":
        x_expr = cx
        y_expr = f"{cy}+(ih-ih/zoom)/2*0.85*(2*on/{n}-1)"
    elif effect in ("shake_soft", "zoom_shake"):
        x_expr = shake_x
        y_expr = shake_y
    else:  # zoom_in / zoom_out / zoom_breathe: centred window
        x_expr = cx
        y_expr = cy

    return (
        f"zoompan=z='{zt}':d=1:x='{x_expr}':y='{y_expr}':"
        f"s={w}x{h}:fps={fps_i},format=yuv420p"
    )


# --------------------------------------------------------------------------
# Extra effects (v1.1) — optional, per-clip random, on top of the main effect
# --------------------------------------------------------------------------

# Extra-effect roll ranges (locked, v1.1):
# - flip: 50% chance per clip when enabled (not every clip — text in a
#   flipped clip reads backwards, and an all-flipped run is a monotonous
#   pattern that is easier to fingerprint as a whole).
# - speed: uniform 0.92-1.08 (2 decimals). Applied with setpts, so the
#   OUTPUT clip duration = planned duration / speed (changes +/-8%).
# - rotate: magnitude uniform 0.5-2.0 degrees (1 decimal), sign +/- random.
#   Applied with an overscale first (see build_extra_filter) so no black
#   corners appear.
SPEED_MIN = 0.92
SPEED_MAX = 1.08
ROTATE_MIN_DEG = 0.5
ROTATE_MAX_DEG = 2.0
ROTATE_OVERSCALE = 1.08


def roll_extra_effects(rng: Optional[random.Random] = None,
                       flip_on: bool = True, speed_on: bool = True,
                       rotate_on: bool = True) -> dict:
    """Roll the optional extra effects for ONE clip.

    Returns {"flip": bool, "speed": float|None, "rotate_deg": float|None}.
    Each roll is independent per clip; flip is a 50% coin toss.
    All-off -> {"flip": False, "speed": None, "rotate_deg": None}.
    """
    r = rng or random
    flip = bool(flip_on and r.random() < 0.5)
    speed = round(r.uniform(SPEED_MIN, SPEED_MAX), 2) if speed_on else None
    rotate_deg = None
    if rotate_on:
        sign = r.choice((-1, 1))
        rotate_deg = round(sign * r.uniform(ROTATE_MIN_DEG, ROTATE_MAX_DEG), 1)
    return {"flip": flip, "speed": speed, "rotate_deg": rotate_deg}


def format_extra_effects(extras: Optional[dict]) -> str:
    """Human-readable extras, e.g. 'flip + speed 1.05x + rotate -1.2°'."""
    if not extras:
        return ""
    parts = []
    if extras.get("flip"):
        parts.append("flip")
    if extras.get("speed") is not None:
        parts.append(f"speed {extras['speed']:.2f}x")
    if extras.get("rotate_deg") is not None:
        parts.append(f"rotate {extras['rotate_deg']:+.1f}°")
    return " + ".join(parts)


def build_extra_filter(width: int, height: int,
                       extras: Optional[dict],
                       fps: float = 30.0) -> str:
    """ffmpeg -vf segment for the extra effects ("" when none active).

    Chain order (after the main zoompan effect): rotate -> hflip ->
    setpts. The caller appends this between the main effect and
    the final format=yuv420p.

    Rotate: overscale ~1.08x first, then rotate, then centre-crop back
    to WxH. 1.08 hides the corners at <=2 deg for any aspect ratio
    (worst case needs ~1.067 at 16:9, from 1/(cos - (W/H)*sin)).
    All dimensions are even (yuv420p).
    Speed: setpts=PTS/speed ONLY — no fps filter after it. Verified
    2026-11-09: `setpts` + `fps=30` after zoompan BLOWS UP the clip
    (~512x frame duplication: a 3.7s clip came out as 56,888 frames /
    31 minutes, time_base 1/15360 = 30*512 — the fps filter misreads
    zoompan's timestamps after setpts; `start_time=0` does not fix
    it). setpts alone is correct: 2.0s at 1.08x -> 56 frames, 1.87s,
    avg_frame_rate still 30/1, duration = planned/speed. The MP4
    muxer's default CFR vsync normalises the frame rate, so the
    output fps stays constant without the fps filter.
    """
    if not extras:
        return ""
    parts = []
    w = _even(width)
    h = _even(height)
    deg = extras.get("rotate_deg")
    if deg is not None:
        sw = _even(w * ROTATE_OVERSCALE)
        sh = _even(h * ROTATE_OVERSCALE)
        rad = float(deg) * 3.141592653589793 / 180.0
        parts.append(
            f"scale={sw}x{sh},rotate={rad:.6f}:fillcolor=black,"
            f"crop={w}:{h}:(in_w-out_w)/2:(in_h-out_h)/2"
        )
    if extras.get("flip"):
        parts.append("hflip")
    speed = extras.get("speed")
    if speed is not None:
        parts.append(f"setpts=PTS/{float(speed):.2f}")
    return ",".join(parts)


# --------------------------------------------------------------------------
# Clip planning (pure logic)
# --------------------------------------------------------------------------

def plan_clips(total: float, min_dur: float, max_dur: float,
               rng: Optional[random.Random] = None) -> List[float]:
    """Split `total` seconds into clip durations.

    Each duration is random uniform in [min_dur, max_dur], except the
    tail: if the remainder after the last full clip is < min_dur, it
    is MERGED into the last clip (last clip may grow to at most
    max_dur + min_dur). Never emits a tiny <min_dur clip, except when
    the whole video itself is shorter than min_dur (one clip = whole
    video). The durations sum to `total` (within float rounding).
    """
    if total <= 0:
        return []
    if min_dur <= 0 or max_dur < min_dur:
        raise ValueError(f"min/max durasi tidak valid: {min_dur}/{max_dur}")
    if total <= min_dur:
        return [float(total)]
    r = rng or random
    durations: List[float] = []
    remaining = float(total)
    while remaining > max_dur:
        # Pick d so the leftover stays >= min_dur (or gets merged later).
        upper = min(max_dur, remaining - min_dur)
        d = r.uniform(min_dur, upper)
        durations.append(d)
        remaining -= d
    if remaining >= min_dur:
        durations.append(remaining)
    else:
        # Tail remainder < min_dur: merge into the last clip.
        if durations:
            durations[-1] += remaining
        else:
            durations.append(remaining)
    return durations


def assign_effects(n: int, rng: Optional[random.Random] = None) -> List[str]:
    """Assign one effect per clip from the shuffled 8-effect pool.

    The pool is shuffled, used in full, then reshuffled for the next
    cycle — so no effect repeats until all 8 have been used once.
    Adjacent clips never share an effect, including across a cycle
    boundary (fixed by swapping the first two of the new cycle).
    """
    if n <= 0:
        return []
    r = rng or random
    out: List[str] = []
    while len(out) < n:
        cycle = list(EFFECTS)
        r.shuffle(cycle)
        if out and cycle[0] == out[-1]:
            cycle[0], cycle[1] = cycle[1], cycle[0]
        out.extend(cycle)
    return out[:n]


# --------------------------------------------------------------------------
# Random output names
# --------------------------------------------------------------------------

_NAME_CHARS = string.ascii_lowercase + string.digits


def random_output_name(rng: Optional[random.Random] = None,
                       length: int = 10) -> str:
    """Random filename stem, e.g. 'a7k9x2q4m1' — never sequential."""
    r = rng or random
    return "".join(r.choice(_NAME_CHARS) for _ in range(length))


def unique_random_output_path(folder: str,
                              rng: Optional[random.Random] = None,
                              length: int = 10) -> str:
    """Random .mp4 path in `folder` that does not exist yet
    (regenerate on collision)."""
    while True:
        cand = os.path.join(folder, random_output_name(rng, length) + ".mp4")
        if not os.path.exists(cand):
            return cand


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_clip(input_path: str, start: float, duration: float,
                output_path: str, effect: str,
                intensity: str = DEFAULT_INTENSITY,
                width: int = 0, height: int = 0, fps: float = 30.0,
                encoder: Optional[str] = None,
                log: LogFn = _noop_log,
                ffmpeg: Optional[str] = None,
                extras: Optional[dict] = None) -> bool:
    """Render ONE clip: -ss start, -t duration, effect filter,
    audio removed totally (-an), re-encode at high quality.

    `extras` is a dict from roll_extra_effects (v1.1): the extra
    filters are appended after the main zoompan effect
    (rotate -> hflip -> setpts -> format). None or all-off means
    byte-identical behaviour to v1 — the filter chain is untouched.
    The extras used are logged per clip (and visible in the logged
    ffmpeg command line). Speed changes the OUTPUT duration to
    duration/speed.

    "Sikat aja": success = ffmpeg exit 0 + output file exists
    and is non-empty. No probe-based verification.
    """
    ff = find_ffmpeg(ffmpeg)
    if width <= 0 or height <= 0:
        log("  render gagal: ukuran video tidak diketahui (probe gagal)")
        return False
    try:
        vf = build_effect_filter(width, height, effect, intensity, duration, fps)
    except ValueError as e:
        log(f"  render gagal: {e}")
        return False
    extras_str = build_extra_filter(width, height, extras or {}, fps)
    if extras_str:
        if vf.endswith(",format=yuv420p"):
            vf = vf[:-len(",format=yuv420p")]
        vf = vf + "," + extras_str + ",format=yuv420p"
        desc = format_extra_effects(extras)
        if desc:
            log(f"  extras: {desc}")
    v_args = video_encoder_args(encoder)
    cmd = ([ff, "-hide_banner", "-y",
            "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
            "-i", input_path,
            "-vf", vf, "-an"] + v_args +
           ["-movflags", "+faststart", output_path])
    r = _run(cmd, log)
    return (r.returncode == 0 and os.path.isfile(output_path)
            and os.path.getsize(output_path) > 0)
