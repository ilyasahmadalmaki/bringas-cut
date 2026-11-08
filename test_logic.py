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
        test_gpu_detection()
        test_video_encoder_args()
        test_detect_gpu_encoder_live()
        test_integration_ffmpeg(tmp)
    print(f"\n{PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
