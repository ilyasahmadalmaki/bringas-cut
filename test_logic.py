"""
Self-test Bringas Cut — pure logic + (if ffmpeg exists) integration.
Run:  python3 test_logic.py
Exit code 0 = all passed.
"""
from __future__ import annotations

import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ffmpeg_utils as fu

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}  {detail}")


def test_plan_clips():
    for total, mn, mx in ((300.0, 3.0, 8.0), (60.0, 3.0, 8.0),
                          (10.0, 3.0, 8.0), (100.0, 5.0, 5.0),
                          (7.5, 3.0, 8.0), (3.0, 3.0, 8.0),
                          (1000.0, 3.0, 8.0)):
        for seed in (0, 1, 42, 1234):
            ds = fu.plan_clips(total, mn, mx, rng=random.Random(seed))
            check(f"plan {total}s {mn}-{mx} seed {seed}: jumlah == total",
                  abs(sum(ds) - total) < 1e-6, f"sum={sum(ds)} ds={ds}")
            check(f"plan {total}s {mn}-{mx} seed {seed}: tidak ada klip mungil",
                  all(d >= mn - 1e-9 or len(ds) == 1 for d in ds), str(ds))
            check(f"plan {total}s {mn}-{mx} seed {seed}: klip <= max+min",
                  all(d <= mx + mn + 1e-9 for d in ds), str(ds))
            if total > mx:
                check(f"plan {total}s {mn}-{mx} seed {seed}: bukan 1 klip",
                      len(ds) > 1, str(ds))
    # Whole video shorter than Min -> one clip = whole video
    ds = fu.plan_clips(2.0, 3.0, 8.0, rng=random.Random(0))
    check("plan: video 2s < min 3s -> 1 klip 2s", ds == [2.0], str(ds))
    ds = fu.plan_clips(0.0, 3.0, 8.0)
    check("plan: total 0 -> []", ds == [], str(ds))
    for bad in ((100.0, 0.0, 8.0), (100.0, 8.0, 3.0), (100.0, -1.0, 8.0)):
        try:
            fu.plan_clips(*bad)
            check(f"plan: min/max tidak valid {bad} -> ValueError", False)
        except ValueError:
            check(f"plan: min/max tidak valid {bad} -> ValueError", True)
    # Durations actually vary (random, not fixed)
    ds = fu.plan_clips(300.0, 3.0, 8.0, rng=random.Random(7))
    check("plan: durasi klip bervariasi (random)",
          len(set(round(d, 2) for d in ds)) > 5, str(ds[:8]))


def test_assign_effects():
    for n in (1, 3, 8, 9, 16, 17, 25, 40):
        for seed in (0, 1, 99):
            effs = fu.assign_effects(n, rng=random.Random(seed))
            check(f"effects n={n} seed {seed}: panjang == n",
                  len(effs) == n, str(effs))
            check(f"effects n={n} seed {seed}: semua dari pool",
                  all(e in fu.EFFECTS for e in effs), str(effs))
            check(f"effects n={n} seed {seed}: tidak ada 2 berurutan sama",
                  all(a != b for a, b in zip(effs, effs[1:])), str(effs))
            if n >= 8:
                check(f"effects n={n} seed {seed}: 8 pertama semuanya beda",
                      len(set(effs[:8])) == 8, str(effs[:8]))
    # Cycle boundary: force many cycles, check boundary never equal
    effs = fu.assign_effects(80, rng=random.Random(5))
    check("effects n=80: tidak ada 2 berurutan sama (semua cycle)",
          all(a != b for a, b in zip(effs, effs[1:])), str(effs))
    check("effects n=0 -> []", fu.assign_effects(0) == [])


def test_random_names():
    pat = re.compile(r"^[a-z0-9]{10}$")
    names = [fu.random_output_name(rng=random.Random(i)) for i in range(200)]
    check("nama: format 10 char [a-z0-9]",
          all(pat.match(n) for n in names), str(names[:5]))
    check("nama: 200 nama semuanya beda (acak, bukan urutan)",
          len(set(names)) == 200)
    check("nama: tidak ada yang berurutan / berpola klip_01",
          all("klip" not in n for n in names))
    check("nama: panjang custom 10 default",
          len(fu.random_output_name()) == 10)


def test_unique_random_path(tmp):
    p1 = fu.unique_random_output_path(tmp, rng=random.Random(1))
    check("unique random: .mp4 di folder yang diminta",
          p1.endswith(".mp4") and os.path.dirname(p1) == tmp, p1)
    Path(p1).write_bytes(b"x")
    p2 = fu.unique_random_output_path(tmp, rng=random.Random(1))
    check("unique random: tabrakan -> nama lain diregenerasi",
          p2 != p1 and not os.path.exists(p2), f"{p1} vs {p2}")


def test_intensity_presets():
    order = ["Lembut banget", "Lembut", "Guncang"]
    zooms = [fu.INTENSITY_PRESETS[k]["zoom"] for k in order]
    shakes = [fu.INTENSITY_PRESETS[k]["shake"] for k in order]
    freqs = [fu.INTENSITY_PRESETS[k]["freq"] for k in order]
    check("intensitas: zoom naik Lembut banget < Lembut < Guncang",
          zooms == sorted(zooms) and len(set(zooms)) == 3, str(zooms))
    check("intensitas: shake naik Lembut banget < Lembut < Guncang",
          shakes == sorted(shakes) and len(set(shakes)) == 3, str(shakes))
    check("intensitas: freq naik Lembut banget < Lembut < Guncang",
          freqs == sorted(freqs) and len(set(freqs)) == 3, str(freqs))
    check("intensitas: default = Lembut", fu.DEFAULT_INTENSITY == "Lembut")
    check("intensitas: 3 opsi", set(fu.INTENSITIES) == set(order))


def test_effect_filter():
    for eff in fu.EFFECTS:
        f1 = fu.build_effect_filter(1920, 1080, eff, "Lembut", 5.0, fps=30.0)
        check(f"filter {eff}: pakai zoompan",
              f1.startswith("zoompan="), f1)
        check(f"filter {eff}: output s=1920x1080 + fps=30",
              "s=1920x1080" in f1 and "fps=30" in f1, f1)
        check(f"filter {eff}: format yuv420p",
              f1.endswith("format=yuv420p"), f1)
    # Filters differ per effect
    fs = {e: fu.build_effect_filter(1280, 720, e, "Lembut", 5.0, fps=30.0)
          for e in fu.EFFECTS}
    check("filter: 8 efek menghasilkan 8 string filter beda",
          len(set(fs.values())) == 8, str(fs))
    # Filters differ per intensity (zoom value changes)
    f_soft = fu.build_effect_filter(1280, 720, "zoom_in", "Lembut banget", 5.0)
    f_mid = fu.build_effect_filter(1280, 720, "zoom_in", "Lembut", 5.0)
    f_hard = fu.build_effect_filter(1280, 720, "zoom_in", "Guncang", 5.0)
    check("filter: intensitas mengubah zoom (1.06 / 1.12 / 1.20)",
          "1.0600" in f_soft and "1.1200" in f_mid and "1.2000" in f_hard,
          f"{f_soft} | {f_mid} | {f_hard}")
    # Odd dimensions get rounded to even (yuv420p)
    f_odd = fu.build_effect_filter(1919, 1079, "zoom_in", "Lembut", 5.0)
    check("filter: dimensi ganjil dibulatkan genap",
          "s=1920x1080" in f_odd, f_odd)
    try:
        fu.build_effect_filter(640, 360, "efek_ngawur", "Lembut", 5.0)
        check("filter: efek tidak dikenal -> ValueError", False)
    except ValueError:
        check("filter: efek tidak dikenal -> ValueError", True)


def test_roll_extra_effects():
    # All off -> nothing
    e = fu.roll_extra_effects(random.Random(0), False, False, False)
    check("extras roll: semua OFF -> flip False, speed/rotate None",
          e == {"flip": False, "speed": None, "rotate_deg": None}, str(e))
    # Flip ~50% in a big sample (seed 42 gives exactly 50/100)
    r = random.Random(42)
    flips = sum(1 for _ in range(100)
                if fu.roll_extra_effects(r, True, False, False)["flip"])
    check("extras roll: flip kira-kira 50% (35-65 dari 100)",
          35 <= flips <= 65, f"flips={flips}")
    # Speed range + 2 decimals, None when off
    r = random.Random(3)
    speeds = [fu.roll_extra_effects(r, False, True, False)["speed"]
              for _ in range(100)]
    check("extras roll: speed dalam [0.92, 1.08]",
          all(0.92 <= s <= 1.08 for s in speeds), str(speeds[:5]))
    check("extras roll: speed dibulatkan 2 desimal",
          all(round(s, 2) == s for s in speeds), str(speeds[:5]))
    check("extras roll: speed bervariasi (random)",
          len(set(speeds)) > 10, str(speeds[:8]))
    check("extras roll: speed OFF -> None",
          fu.roll_extra_effects(random.Random(0), False, False, False)["speed"] is None)
    # Rotate magnitude + sign, None when off
    r = random.Random(5)
    rots = [fu.roll_extra_effects(r, False, False, True)["rotate_deg"]
            for _ in range(100)]
    check("extras roll: |rotate| dalam [0.5, 2.0]",
          all(0.5 <= abs(d) <= 2.0 for d in rots), str(rots[:5]))
    check("extras roll: rotate dibulatkan 1 desimal",
          all(round(d, 1) == d for d in rots), str(rots[:5]))
    check("extras roll: rotate ada + dan - (arah acak)",
          any(d > 0 for d in rots) and any(d < 0 for d in rots), str(rots[:10]))
    check("extras roll: rotate OFF -> None",
          fu.roll_extra_effects(random.Random(0), False, False, False)["rotate_deg"] is None)
    # Keys
    e = fu.roll_extra_effects(random.Random(0))
    check("extras roll: keys = flip/speed/rotate_deg",
          set(e.keys()) == {"flip", "speed", "rotate_deg"}, str(e))
    # format helper
    check("extras format: flip + speed + rotate",
          fu.format_extra_effects({"flip": True, "speed": 1.05, "rotate_deg": -1.2})
          == "flip + speed 1.05x + rotate -1.2°")
    check("extras format: semua off -> ''",
          fu.format_extra_effects({"flip": False, "speed": None, "rotate_deg": None}) == "")
    check("extras format: None -> ''", fu.format_extra_effects(None) == "")


def test_build_extra_filter():
    none_ex = {"flip": False, "speed": None, "rotate_deg": None}
    check("extra filter: tidak ada yang aktif -> ''",
          fu.build_extra_filter(640, 360, none_ex) == "")
    check("extra filter: extras None -> ''",
          fu.build_extra_filter(640, 360, None) == "")
    f = fu.build_extra_filter(640, 360, {"flip": True, "speed": None, "rotate_deg": None})
    check("extra filter: flip saja -> hflip, tanpa setpts/rotate",
          f == "hflip", f)
    f = fu.build_extra_filter(640, 360, {"flip": False, "speed": 1.05, "rotate_deg": None})
    check("extra filter: speed saja -> setpts saja, tanpa hflip/rotate/fps",
          f == "setpts=PTS/1.05", f)
    # NO fps filter after setpts: verified 2026-11-09, fps filter after
    # zoompan+setpts duplicates frames ~512x (3.7s clip -> 56,888 frames).
    # setpts alone is correct; the muxer's CFR vsync keeps fps constant.
    check("extra filter: speed TIDAK pakai fps filter (bug 512x)",
          "fps=" not in fu.build_extra_filter(
              640, 360, {"flip": False, "speed": 1.08, "rotate_deg": None}, fps=25.0))
    f = fu.build_extra_filter(640, 360, {"flip": False, "speed": None, "rotate_deg": 1.5})
    check("extra filter: rotate saja -> scale + rotate + crop, tanpa hflip/setpts",
          "rotate=" in f and "crop=640:360" in f and "scale=" in f
          and "hflip" not in f and "setpts" not in f, f)
    # Rotate overscale: 640*1.08 = 691.2 -> 692 (even); 360*1.08 = 388.8 -> 388
    check("extra filter: rotate overscale 1.08x dibulatkan genap",
          f.startswith("scale=692x388,"), f)
    # Order: rotate -> hflip -> setpts
    f = fu.build_extra_filter(640, 360, {"flip": True, "speed": 0.95, "rotate_deg": -1.2})
    check("extra filter: semua aktif -> urutan rotate, hflip, setpts",
          f.index("rotate=") < f.index("hflip") < f.index("setpts="), f)


def test_is_youtube_url():
    good = [
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "https://youtube.com/watch?v=jNQXAC9IVRw&t=5s",
        "http://www.youtube.com/watch?v=abc123XYZ-_",
        "www.youtube.com/watch?v=abc123XYZ-_",
        "https://www.youtube.com/shorts/abc123XYZ-_",
        "https://youtube.com/shorts/abc123XYZ-_?feature=share",
        "https://youtu.be/jNQXAC9IVRw",
        "youtu.be/jNQXAC9IVRw?t=10",
        "https://music.youtube.com/watch?v=abc123XYZ-_",
        "https://m.youtube.com/watch?v=abc123XYZ-_",
        "https://www.youtube.com/embed/abc123XYZ-_",
        "https://www.youtube.com/live/abc123XYZ-_",
        "https://www.youtube.com/watch?v=abc123XYZ-_&list=PL123456",
    ]
    for u in good:
        check(f"yt url: diterima {u[:45]}", fu.is_youtube_url(u) is True, u)
    bad = [
        "", "   ", "bukan url", "https://vimeo.com/123456",
        "https://www.facebook.com/watch/?v=123",
        "https://www.tiktok.com/@x/video/123",
        "https://www.youtube.com/", "https://youtube.com",
        "https://youtu.be/", "youtu.be/",
        "https://www.youtube.com/playlist?list=PL123456",
        "https://www.youtube.com/channel/UC123456",
        "https://www.google.com/search?q=youtube",
    ]
    for u in bad:
        check(f"yt url: ditolak {u[:45]!r}", fu.is_youtube_url(u) is False, u)


def test_youtube_url_problem():
    check("yt problem: URL ok -> None",
          fu.youtube_url_problem("https://youtu.be/jNQXAC9IVRw") is None)
    check("yt problem: kosong -> pesan",
          fu.youtube_url_problem("") is not None)
    check("yt problem: domain lain -> pesan",
          fu.youtube_url_problem("https://vimeo.com/123") is not None)
    check("yt problem: playlist saja -> pesan playlist",
          "playlist" in (fu.youtube_url_problem(
              "https://www.youtube.com/playlist?list=PL123") or "").lower())
    check("yt problem: watch+list -> None (video itu yang di-download)",
          fu.youtube_url_problem(
              "https://www.youtube.com/watch?v=abc123XYZ-_&list=PL123") is None)


def test_build_ytdlp_command():
    cmd = fu.build_ytdlp_command("/usr/bin/yt-dlp",
                                 "https://youtu.be/jNQXAC9IVRw",
                                 "/tmp/dl/Judul.%(ext)s")
    check("ytdlp cmd: executable + url di akhir",
          cmd[0] == "/usr/bin/yt-dlp" and cmd[-1] == "https://youtu.be/jNQXAC9IVRw",
          str(cmd))
    check("ytdlp cmd: --no-playlist (bukan playlist)",
          "--no-playlist" in cmd, str(cmd))
    check("ytdlp cmd: --newline (progress bisa di-parse)",
          "--newline" in cmd, str(cmd))
    check("ytdlp cmd: --merge-output-format mp4",
          "--merge-output-format" in cmd and "mp4" in cmd, str(cmd))
    fmt = cmd[cmd.index("-f") + 1]
    check("ytdlp cmd: format cap height<=1080",
          "height<=1080" in fmt, fmt)
    check("ytdlp cmd: format TIDAK pernah di atas 1080 (tanpa 2160/4320)",
          "2160" not in fmt and "4320" not in fmt, fmt)
    check("ytdlp cmd: format minta mp4 dulu",
          "[ext=mp4]" in fmt, fmt)
    check("ytdlp cmd: -o template dipakai",
          cmd[cmd.index("-o") + 1] == "/tmp/dl/Judul.%(ext)s", str(cmd))
    check("ytdlp cmd: extractor-args android dulu, web fallback",
          "android,web" in cmd[cmd.index("--extractor-args") + 1], str(cmd))


def test_parse_ytdlp_progress():
    check("progress: 45.2% standar",
          fu.parse_ytdlp_progress("[download]  45.2% of  12.34MiB at  1.20MiB/s ETA 00:05") == 45.2)
    check("progress: 2.4% (spasi ganda)",
          fu.parse_ytdlp_progress("[download]   2.4% of  614.43KiB at  400.48KiB/s ETA 00:01") == 2.4)
    check("progress: 100% tanpa desimal",
          fu.parse_ytdlp_progress("[download] 100% of  614.43KiB in 00:00:01 at 400.54KiB/s") == 100.0)
    check("progress: 100.0% dengan desimal",
          fu.parse_ytdlp_progress("[download] 100.0% of  614.43KiB at  1.92MiB/s ETA 00:00") == 100.0)
    check("progress: 0%",
          fu.parse_ytdlp_progress("[download]   0.0% of  10.00MiB at  1.00MiB/s ETA 00:10") == 0.0)
    check("progress: Destination -> None",
          fu.parse_ytdlp_progress("[download] Destination: video.mp4") is None)
    check("progress: baris ffmpeg -> None",
          fu.parse_ytdlp_progress("[ffmpeg] Merging formats into \"video.mp4\"") is None)
    check("progress: baris kosong -> None",
          fu.parse_ytdlp_progress("") is None)
    check("progress: info biasa -> None",
          fu.parse_ytdlp_progress("[youtube] jNQXAC9IVRw: Downloading webpage") is None)


def test_find_yt_dlp(tmp):
    import shutil as _shutil
    # Explicit path ke file palsu -> dipakai
    fake = os.path.join(tmp, "yt-dlp.exe")
    Path(fake).write_bytes(b"fake")
    check("find ytdlp: explicit yang ada -> dipakai",
          fu.find_yt_dlp(fake) == fake)
    # Explicit tidak ada -> jatuh ke pencarian lain (bukan crash, dan
    # hasilnya sama dengan pencarian tanpa explicit)
    check("find ytdlp: explicit tidak ada -> sama kayak tanpa explicit",
          fu.find_yt_dlp(os.path.join(tmp, "tidak_ada.exe")) == fu.find_yt_dlp())
    # PATH mock: bikin 'yt-dlp' palsu di folder PATH sendiri
    bindir = os.path.join(tmp, "bin")
    os.makedirs(bindir, exist_ok=True)
    fake_bin = os.path.join(bindir, "yt-dlp")
    Path(fake_bin).write_text("#!/bin/sh\necho fake\n")
    os.chmod(fake_bin, 0o755)
    old_path = os.environ.get("PATH", "")
    try:
        os.environ["PATH"] = bindir  # tidak ada yt-dlp asli di PATH ini
        got = fu.find_yt_dlp()
        check("find ytdlp: ketemu di PATH",
              got == fake_bin, str(got))
        # PATH kosong dari yt-dlp -> None (bukan string buta)
        empty = os.path.join(tmp, "emptybin")
        os.makedirs(empty, exist_ok=True)
        os.environ["PATH"] = empty
        check("find ytdlp: tidak ada di mana-mana -> None",
              fu.find_yt_dlp() is None, str(fu.find_yt_dlp()))
    finally:
        os.environ["PATH"] = old_path


def test_sanitize_and_numbered_path(tmp):
    check("sanitize: karakter ilegal -> _",
          fu.sanitize_filename('a/b:c*d?e"f<g>h|i') == "a_b_c_d_e_f_g_h_i")
    check("sanitize: spasi beruntun -> 1 underscore",
          fu.sanitize_filename("Judul  Video   Tes") == "Judul_Video_Tes")
    check("sanitize: kosong -> 'video'",
          fu.sanitize_filename("   ") == "video")
    check("sanitize: max 120 char",
          len(fu.sanitize_filename("x" * 200)) == 120)
    p = os.path.join(tmp, "Judul.mp4")
    check("numbered: belum ada -> sama",
          fu.unique_numbered_path(p) == p)
    Path(p).write_bytes(b"x")
    check("numbered: sudah ada -> (1)",
          fu.unique_numbered_path(p) == os.path.join(tmp, "Judul (1).mp4"))
    Path(os.path.join(tmp, "Judul (1).mp4")).write_bytes(b"x")
    check("numbered: (1) ada -> (2)",
          fu.unique_numbered_path(p) == os.path.join(tmp, "Judul (2).mp4"))
    check("numbered: minta 'Judul (1)' lagi -> (2)",
          fu.unique_numbered_path(os.path.join(tmp, "Judul (1).mp4"))
          == os.path.join(tmp, "Judul (2).mp4"))


def test_download_target_path(tmp):
    dl = os.path.join(tmp, "downloads")
    os.makedirs(dl, exist_ok=True)
    tmpl, exp = fu.download_target_path(dl, "Me at the zoo")
    check("target: template pakai %(ext)s",
          tmpl == os.path.join(dl, "Me_at_the_zoo.%(ext)s"), tmpl)
    check("target: expected .mp4",
          exp == os.path.join(dl, "Me_at_the_zoo.mp4"), exp)
    Path(exp).write_bytes(b"x")
    tmpl2, exp2 = fu.download_target_path(dl, "Me at the zoo")
    check("target: tabrakan -> (1), template ikut",
          exp2 == os.path.join(dl, "Me_at_the_zoo (1).mp4") and
          tmpl2 == os.path.join(dl, "Me_at_the_zoo (1).%(ext)s"),
          f"{tmpl2} | {exp2}")
    tmpl3, exp3 = fu.download_target_path(dl, "Judul: Ada/Tanda? *Terlarang*")
    check("target: judul kotor di-sanitize",
          os.path.basename(exp3) == "Judul__Ada_Tanda___Terlarang_.mp4", exp3)


_FAKE_YTDLP = '''#!/usr/bin/env python3
"""yt-dlp PALSU buat tes: meniru --get-title/--get-duration/download."""
import os, shutil, sys

args = sys.argv[1:]
if os.environ.get("FAKE_YT_FAIL") == "1":
    print("ERROR: Video ini private", file=sys.stderr)
    sys.exit(1)
if "--get-title" in args:
    print("Video Tes Palsu")
    if "--get-duration" in args:
        print("10")
    sys.exit(0)
if "-o" in args:
    tmpl = args[args.index("-o") + 1]
    out = tmpl.replace("%(ext)s", "mp4")
    print("[download]  50.0% of  1.00MiB at  1.00MiB/s ETA 00:00")
    print("[download] 100.0% of  1.00MiB at  1.00MiB/s ETA 00:00")
    print("[download] Destination: " + out)
    src = os.environ.get("FAKE_YT_SRC", "")
    if src and os.path.isfile(src):
        shutil.copyfile(src, out)
    else:
        open(out, "wb").write(b"fake-mp4")
    sys.exit(0)
print("ERROR: argumen tidak dikenal", file=sys.stderr)
sys.exit(1)
'''


def _make_fake_ytdlp(tmp):
    fake = os.path.join(tmp, "yt-dlp")
    Path(fake).write_text(_FAKE_YTDLP)
    os.chmod(fake, 0o755)
    return fake


def test_get_youtube_info_fake(tmp):
    fake = _make_fake_ytdlp(tmp)
    info = fu.get_youtube_info(fake, "https://youtu.be/FAKE1234567")
    check("yt info palsu: judul + durasi terbaca",
          info == {"title": "Video Tes Palsu", "duration": 10.0}, str(info))
    # Mode gagal -> None (bukan exception)
    os.environ["FAKE_YT_FAIL"] = "1"
    try:
        check("yt info palsu: gagal -> None",
              fu.get_youtube_info(fake, "https://youtu.be/FAKE1234567") is None)
    finally:
        del os.environ["FAKE_YT_FAIL"]


def test_download_youtube_fake(tmp):
    fake = _make_fake_ytdlp(tmp)
    # Sumber "video" beneran buat disalin si fake yt-dlp
    src = os.path.join(tmp, "src.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:d=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", src],
        capture_output=True, text=True)
    if r.returncode != 0:
        print("SKIP  download fake: ffmpeg gagal bikin src")
        return
    os.environ["FAKE_YT_SRC"] = src
    try:
        dl = os.path.join(tmp, "downloads")
        os.makedirs(dl, exist_ok=True)
        tmpl, exp = fu.download_target_path(dl, "Video Tes Palsu")
        seen = []
        ok, result = fu.download_youtube_video(
            fake, "https://youtu.be/FAKE1234567", tmpl, exp,
            log=lambda m: None, progress_cb=lambda p: seen.append(p))
        check("download palsu: ok + path sesuai expected",
              ok and result == exp, f"ok={ok} result={result}")
        check("download palsu: file ada + isinya = src",
              os.path.isfile(exp) and Path(exp).read_bytes() == Path(src).read_bytes())
        check("download palsu: progress callback dipanggil (50% + 100%)",
              50.0 in seen and 100.0 in seen, str(seen))
        # Mode gagal -> (False, error tail berisi pesan)
        os.environ["FAKE_YT_FAIL"] = "1"
        tmpl2, exp2 = fu.download_target_path(dl, "Video Gagal")
        ok2, err = fu.download_youtube_video(
            fake, "https://youtu.be/FAKE1234567", tmpl2, exp2, log=lambda m: None)
        check("download palsu: gagal -> False + error tail ada isinya",
              ok2 is False and err and "private" in err, str(err))
        check("download palsu: gagal -> file TIDAK dibuat",
              not os.path.exists(exp2))
    finally:
        os.environ.pop("FAKE_YT_SRC", None)
        os.environ.pop("FAKE_YT_FAIL", None)


def test_gpu_detection():
    fake_all = (
        "Encoders:\n"
        " V..... = Video\n"
        " ------\n"
        " V..... libx264              libx264 H.264 / AVC (codec h264)\n"
        " V..... h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)\n"
        " V..... h264_qsv             Intel Quick Sync Video H.264 encoder (codec h264)\n"
        " V..... h264_amf             AMD AMF H.264 Video Encoder (codec h264)\n"
    )
    check("gpu: prioritas NVENC saat ketiganya ada",
          fu.parse_encoders_output(fake_all) == "h264_nvenc")
    check("gpu: daftar kandidat urut prioritas",
          fu.parse_encoders_list(fake_all) == ["h264_nvenc", "h264_qsv", "h264_amf"])
    check("gpu: QSV saat NVENC tidak ada",
          fu.parse_encoders_output(" V..... h264_qsv  Intel QSV (codec h264)\n"
                                   " V..... h264_amf  AMD AMF (codec h264)\n") == "h264_qsv")
    check("gpu: AMF saat hanya AMF",
          fu.parse_encoders_output(" V..... h264_amf  AMD AMF (codec h264)\n") == "h264_amf")
    check("gpu: None saat tidak ada hardware encoder",
          fu.parse_encoders_output(" V..... libx264  libx264 (codec h264)\n") is None)
    check("gpu: teks kosong -> None", fu.parse_encoders_output("") is None)


def test_video_encoder_args():
    check("gpu args: default = libx264 crf 18",
          fu.video_encoder_args() == ["-c:v", "libx264", "-crf", "18",
                                      "-preset", "veryfast", "-pix_fmt", "yuv420p"])
    nv = fu.video_encoder_args("h264_nvenc")
    check("gpu args: NVENC pakai p4 + cq 19",
          nv[:4] == ["-c:v", "h264_nvenc", "-preset", "p4"] and "-cq" in nv and "19" in nv,
          str(nv))
    check("gpu args: QSV pakai global_quality",
          "-global_quality" in fu.video_encoder_args("h264_qsv"))
    amf = fu.video_encoder_args("h264_amf")
    check("gpu args: AMF pakai cqp", "-rc" in amf and "cqp" in amf, str(amf))
    check("gpu args: encoder asing -> fallback libx264",
          fu.video_encoder_args("h264_foo") == fu.video_encoder_args())


def test_detect_gpu_encoder_live():
    # Same lesson as Bringas: `ffmpeg -encoders` alone is NOT proof —
    # this VM lists h264_nvenc but the 1-frame probe must reject it.
    enc1 = fu.detect_gpu_encoder()
    enc2 = fu.detect_gpu_encoder()
    check("gpu detect: hasil valid (None atau encoder dikenal)",
          enc1 is None or enc1 in fu._GPU_ENCODERS, str(enc1))
    check("gpu detect: hasil konsisten (cache)", enc1 == enc2)
    check("gpu detect: probe menolak encoder yang tidak dikenal",
          fu._encoder_probe_ok(fu.find_ffmpeg(), "h264_tidak_ada") is False)
    check("gpu detect: encoder terdaftar tapi tak bisa jalan -> None",
          enc1 is None)


def _has_audio_stream(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_streams", path], capture_output=True, text=True)
    try:
        data = json.loads(r.stdout or "{}")
    except Exception:
        return None
    return any(s.get("codec_type") == "audio"
               for s in data.get("streams", []))


def test_integration_ffmpeg(tmp):
    if not shutil_which("ffmpeg") or not shutil_which("ffprobe"):
        print("SKIP  integration: ffmpeg/ffprobe tidak tersedia di VM ini")
        return
    print("integration: ffmpeg tersedia, buat video tes 10s 640x360 + audio…")
    src = os.path.join(tmp, "src.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:d=10",
         "-f", "lavfi", "-i", "sine=frequency=440:d=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", src], capture_output=True, text=True)
    check("integration: buat video sumber 10s", r.returncode == 0 and os.path.isfile(src))
    if r.returncode != 0:
        print(r.stderr[-500:])
        return
    check("integration: sumber PUNYA audio (buat ngetes -an)",
          _has_audio_stream(src) is True)
    info = fu.probe_specs(src)
    check("integration: probe sumber 640x360",
          info.width == 640 and info.height == 360, str(info))
    check("integration: probe durasi sumber ~10s",
          abs(info.duration - 10.0) < 0.6, f"dur={info.duration}")

    # Plan 3-5s clips, render 3 clips with different effects
    rng = random.Random(11)
    durations = fu.plan_clips(info.duration, 3.0, 5.0, rng=rng)
    effects = fu.assign_effects(len(durations), rng=rng)
    check("integration: plan 10s -> 2-3 klip",
          2 <= len(durations) <= 3, str(durations))
    out_dir = os.path.join(tmp, "out")
    os.makedirs(out_dir, exist_ok=True)
    starts, t = [], 0.0
    for d in durations:
        starts.append(t)
        t += d
    fps = info.fps if info.fps > 0 else 30.0
    rendered = []
    for i, (start, dur, eff) in enumerate(zip(starts, durations, effects)):
        if i >= 3:
            break
        out = fu.unique_random_output_path(out_dir, rng=random.Random(100 + i))
        ok = fu.render_clip(src, start, dur, out, eff, "Lembut",
                            info.width, info.height, fps,
                            encoder=None, log=lambda m: None)
        check(f"integration: render klip {i + 1} ({eff}, {dur:.1f}s)",
              ok and os.path.isfile(out), out)
        if ok:
            rendered.append((out, dur))
    for out, dur in rendered:
        got = fu.probe_duration(out)
        check(f"integration: durasi klip ~{dur:.1f}s",
              abs(got - dur) < 0.6, f"got={got} want={dur} file={out}")
        spec = fu.probe_specs(out)
        check(f"integration: resolusi klip tetap 640x360",
              spec.width == 640 and spec.height == 360, str(spec))
        check("integration: klip TIDAK punya audio stream",
              _has_audio_stream(out) is False, out)
        check("integration: nama file acak 10 char",
              re.match(r"^[a-z0-9]{10}\.mp4$", os.path.basename(out)) is not None,
              os.path.basename(out))
    # GPU path must not crash either (falls back to CPU here)
    out_cpu = os.path.join(tmp, "gpu_fallback.mp4")
    ok = fu.render_clip(src, 0, 3.0, out_cpu, "shake_soft", "Guncang",
                        640, 360, 30.0, encoder=fu.detect_gpu_encoder(),
                        log=lambda m: None)
    check("integration: render intensitas Guncang + encoder terdeteksi",
          ok and os.path.isfile(out_cpu))


def _extract_frame(video, at, out_png):
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", video,
         "-frames:v", "1", out_png], capture_output=True, text=True)
    return r.returncode == 0 and os.path.isfile(out_png)


def test_integration_extra_effects(tmp):
    if not shutil_which("ffmpeg") or not shutil_which("ffprobe"):
        print("SKIP  integration extras: ffmpeg/ffprobe tidak tersedia di VM ini")
        return
    print("integration extras: buat video tes 10s 640x360 + audio…")
    src = os.path.join(tmp, "src_x.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:d=10",
         "-f", "lavfi", "-i", "sine=frequency=440:d=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", src], capture_output=True, text=True)
    check("integration extras: buat video sumber 10s",
          r.returncode == 0 and os.path.isfile(src))
    if r.returncode != 0:
        return
    info = fu.probe_specs(src)
    fps = info.fps if info.fps > 0 else 30.0
    out_dir = os.path.join(tmp, "out_x")
    os.makedirs(out_dir, exist_ok=True)
    log = lambda m: None
    # (label, start, planned_dur, effect, extras, expected_dur)
    cases = [
        ("flip", 0.0, 3.0, "zoom_in",
         {"flip": True, "speed": None, "rotate_deg": None}, 3.0),
        ("speed 1.08x", 3.0, 4.0, "pan_left",
         {"flip": False, "speed": 1.08, "rotate_deg": None}, 4.0 / 1.08),
        ("speed 0.92x", 0.0, 3.0, "zoom_out",
         {"flip": False, "speed": 0.92, "rotate_deg": None}, 3.0 / 0.92),
        ("rotate 2.0", 3.0, 3.0, "shake_soft",
         {"flip": False, "speed": None, "rotate_deg": 2.0}, 3.0),
        ("kombinasi", 6.0, 3.0, "zoom_breathe",
         {"flip": True, "speed": 0.95, "rotate_deg": -1.0}, 3.0 / 0.95),
    ]
    for label, start, dur, eff, ex, exp_dur in cases:
        out = fu.unique_random_output_path(out_dir, rng=random.Random(200 + len(label)))
        ok = fu.render_clip(src, start, dur, out, eff, "Lembut",
                            info.width, info.height, fps,
                            encoder=None, log=log, extras=ex)
        check(f"integration extras: render {label} ok",
              ok and os.path.isfile(out), out)
        if not ok:
            continue
        got = fu.probe_duration(out)
        check(f"integration extras: durasi {label} ~{exp_dur:.2f}s (rencana {dur:.1f}s)",
              abs(got - exp_dur) < 0.6, f"got={got} want={exp_dur}")
        # Direction check: speed must actually move the duration, not
        # just land inside the loose +/-0.6 tolerance.
        if ex.get("speed") is not None and ex["speed"] > 1.0:
            check(f"integration extras: {label} durasi LEBIH PENDEK dari rencana",
                  got < dur - 0.1, f"got={got} planned={dur}")
        elif ex.get("speed") is not None and ex["speed"] < 1.0:
            check(f"integration extras: {label} durasi LEBIH PANJANG dari rencana",
                  got > dur + 0.1, f"got={got} planned={dur}")
        spec = fu.probe_specs(out)
        check(f"integration extras: resolusi {label} tetap 640x360",
              spec.width == 640 and spec.height == 360, str(spec))
        check(f"integration extras: {label} TIDAK punya audio stream",
              _has_audio_stream(out) is False, out)
    # extras=None / all-off == v1 behaviour (same duration, no extras)
    out_v1 = os.path.join(tmp, "v1_plain.mp4")
    ok = fu.render_clip(src, 0, 3.0, out_v1, "zoom_in", "Lembut",
                        640, 360, fps, encoder=None, log=log, extras=None)
    check("integration extras: extras=None render ok (v1)",
          ok and os.path.isfile(out_v1))
    if ok:
        check("integration extras: extras=None durasi == rencana 3.0s",
              abs(fu.probe_duration(out_v1) - 3.0) < 0.6,
              f"got={fu.probe_duration(out_v1)}")
    # Flip really changes pixels: same segment, plain vs flipped frame
    plain = os.path.join(tmp, "plain.mp4")
    flipped = os.path.join(tmp, "flipped.mp4")
    ok1 = fu.render_clip(src, 1.0, 3.0, plain, "zoom_in", "Lembut",
                         640, 360, fps, encoder=None, log=log,
                         extras={"flip": False, "speed": None, "rotate_deg": None})
    ok2 = fu.render_clip(src, 1.0, 3.0, flipped, "zoom_in", "Lembut",
                         640, 360, fps, encoder=None, log=log,
                         extras={"flip": True, "speed": None, "rotate_deg": None})
    if ok1 and ok2:
        p1 = os.path.join(tmp, "f_plain.png")
        p2 = os.path.join(tmp, "f_flipped.png")
        if _extract_frame(plain, 1.5, p1) and _extract_frame(flipped, 1.5, p2):
            b1 = Path(p1).read_bytes()
            b2 = Path(p2).read_bytes()
            check("integration extras: frame flip BEDA dari frame polos (flip beneran jalan)",
                  b1 != b2, f"plain={len(b1)}B flipped={len(b2)}B")
        else:
            check("integration extras: ekstrak frame buat bandingin flip", False)
    else:
        check("integration extras: render polos+flip buat bandingin frame", False)


def test_integration_fake_download_to_cut(tmp):
    """Alur lengkap download (fake yt-dlp) -> probe -> cincang 1 klip.

    Membuktikan pipeline v1.2 end-to-end tanpa network: file hasil
    'download' langsung jadi sumber potongan, dan klip hasilnya tetap
    tanpa audio.
    """
    if not shutil_which("ffmpeg") or not shutil_which("ffprobe"):
        print("SKIP  integration fake-download->cut: ffmpeg tidak tersedia")
        return
    print("integration fake-download->cut: buat src 10s, download palsu, cincang…")
    src = os.path.join(tmp, "src_dl.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:d=10",
         "-f", "lavfi", "-i", "sine=frequency=440:d=10",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", src], capture_output=True, text=True)
    check("integration fake-download->cut: buat src 10s",
          r.returncode == 0 and os.path.isfile(src))
    if r.returncode != 0:
        return
    fake = _make_fake_ytdlp(tmp)
    os.environ["FAKE_YT_SRC"] = src
    try:
        dl = os.path.join(tmp, "downloads")
        os.makedirs(dl, exist_ok=True)
        tmpl, exp = fu.download_target_path(dl, "Video Tes Palsu")
        ok, result = fu.download_youtube_video(
            fake, "https://youtu.be/FAKE1234567", tmpl, exp, log=lambda m: None)
        check("integration fake-download->cut: download palsu ok",
              ok and result == exp, str(result))
        if not ok:
            return
        info = fu.probe_specs(result)
        check("integration fake-download->cut: probe hasil download ~10s",
              abs(info.duration - 10.0) < 0.6, f"dur={info.duration}")
        check("integration fake-download->cut: hasil download PUNYA audio (sumber)",
              _has_audio_stream(result) is True)
        out_dir = os.path.join(tmp, "out_dl")
        os.makedirs(out_dir, exist_ok=True)
        out = fu.unique_random_output_path(out_dir, rng=random.Random(5))
        ok2 = fu.render_clip(result, 1.0, 3.0, out, "zoom_in", "Lembut",
                             info.width, info.height, 30.0,
                             encoder=None, log=lambda m: None)
        check("integration fake-download->cut: 1 klip ke-render dari hasil download",
              ok2 and os.path.isfile(out))
        if ok2:
            check("integration fake-download->cut: klip TIDAK punya audio stream",
                  _has_audio_stream(out) is False, out)
            spec = fu.probe_specs(out)
            check("integration fake-download->cut: resolusi klip tetap 640x360",
                  spec.width == 640 and spec.height == 360, str(spec))
    finally:
        os.environ.pop("FAKE_YT_SRC", None)


def test_integration_real_youtube(tmp):
    """Download YouTube BENERAN (kalau network VM mengizinkan).

    Video: 'Me at the zoo' (19 detik, publik) — kecil, cepat.
    Kalau yt-dlp tidak ada atau YouTube memblokir IP VM ini (429 /
    bot-check — yang memang terjadi pada client web dari IP proxy
    bersama), tes ini SKIP dengan alasan, bukan FAIL: alur download
    sudah terbukti lewat fake yt-dlp + command yang sama persis.
    Yang dicek kalau download jalan: file .mp4 ada, tinggi <= 1080
    (cap format string), dan sumber hasil download punya audio
    (klip hasil cincang nanti yang harus tidak punya audio).
    """
    ytdlp = shutil_which("yt-dlp")
    if not ytdlp:
        print("SKIP  integration YouTube: yt-dlp tidak tersedia di VM ini")
        return
    print("integration YouTube: cek info 'Me at the zoo' via yt-dlp beneran…")
    info = fu.get_youtube_info(ytdlp, "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                               timeout=90)
    if info is None:
        print("SKIP  integration YouTube: get info gagal "
              "(YouTube memblokir IP VM / network tidak mengizinkan)")
        return
    check("integration YouTube: judul 'Me at the zoo'",
          info["title"] == "Me at the zoo", str(info))
    check("integration YouTube: durasi ~19 detik",
          info["duration"] is not None and abs(info["duration"] - 19) < 2,
          str(info))
    dl = os.path.join(tmp, "yt_real")
    os.makedirs(dl, exist_ok=True)
    tmpl, exp = fu.download_target_path(dl, info["title"])
    ok, result = fu.download_youtube_video(
        ytdlp, "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        tmpl, exp, log=lambda m: None)
    if not ok:
        print(f"SKIP  integration YouTube download: {result}")
        return
    check("integration YouTube: file .mp4 hasil download ada",
          os.path.isfile(result) and result.endswith(".mp4"), str(result))
    spec = fu.probe_specs(result)
    check("integration YouTube: tinggi hasil <= 1080 (cap format string)",
          0 < spec.height <= 1080, str(spec))
    check("integration YouTube: hasil download PUNYA audio (sumber)",
          _has_audio_stream(result) is True)


def shutil_which(name):
    import shutil
    return shutil.which(name)


def main():
    print("== Bringas Cut — self test ==")
    with tempfile.TemporaryDirectory(prefix="bringas_cut_test_") as tmp:
        test_plan_clips()
        test_assign_effects()
        test_random_names()
        test_unique_random_path(tmp)
        test_intensity_presets()
        test_effect_filter()
        test_roll_extra_effects()
        test_build_extra_filter()
        test_is_youtube_url()
        test_youtube_url_problem()
        test_build_ytdlp_command()
        test_parse_ytdlp_progress()
        test_find_yt_dlp(tmp)
        test_sanitize_and_numbered_path(tmp)
        test_download_target_path(tmp)
        test_get_youtube_info_fake(tmp)
        test_download_youtube_fake(tmp)
        test_gpu_detection()
        test_video_encoder_args()
        test_detect_gpu_encoder_live()
        test_integration_ffmpeg(tmp)
        test_integration_extra_effects(tmp)
        test_integration_fake_download_to_cut(tmp)
        test_integration_real_youtube(tmp)
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
