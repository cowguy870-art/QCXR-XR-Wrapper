#!/usr/bin/env python3
"""
Recolors the QCXR-XR-Wrapper Unity project to a purple theme.

Run from the Unity project root (the folder containing Assets/ and ProjectSettings/):
    python3 tools/apply_purple_theme.py            # apply
    python3 tools/apply_purple_theme.py --dry-run  # just report what would change

What it changes (all idempotent, so running twice is harmless):
  * UI colours in Assets/Scenes/*.unity and Assets/Prefabs/*.prefab: any saturated warm colour
    (gold/brown/orange/red) is moved to purple, keeping its saturation and brightness.
  * The green main-button sprite, and the brown/red background sprites, are hue-shifted to purple.
  * The Unity splash-screen background colour.
It does NOT touch: grey/white/black UI, text colours, the Minecraft logo, the Pojav x Vivecraft credit
logo, 3D textures of the cabin room, or lighting. Keep .meta files as-is so Unity references survive.

Requires: Python 3.8+, Pillow (pip install pillow).
"""
import argparse
import colorsys
import glob
import os
import re
import sys

TARGET_HUE_DEG = 270.0          # violet; change to taste (e.g. 280 = more magenta, 260 = bluer)
MIN_SAT = 0.15                  # below this a colour counts as grey and is left alone
WARM = lambda h: h <= 60 or h >= 330   # hue degrees treated as the old "warm" palette

COLOR_KEYS = ("m_Color", "m_SplashScreenBackgroundColor")
COLOR_RE = re.compile(
    r"^(?P<lead>\s*(?:- )?)(?P<key>%s): \{r: (?P<r>[-\d.eE]+), g: (?P<g>[-\d.eE]+), "
    r"b: (?P<b>[-\d.eE]+), a: (?P<a>[-\d.eE]+)\}\s*$" % "|".join(COLOR_KEYS)
)

# Sprites to hue-shift (path relative to project root). Greys are skipped automatically.
SPRITES = [
    "Assets/Resources/UI/MainButton.png",
    "Assets/Resources/UI/Background.png",
    "Assets/Resources/questerBackground.png",
]


def fmt(x):
    s = ("%.8f" % x).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


SPLASH_BG = (0.12, 0.08, 0.17)  # dark purple


def recolor_line(line):
    m = COLOR_RE.match(line.rstrip("\n"))
    if not m:
        return line, False
    if m.group("key") == "m_SplashScreenBackgroundColor":
        new = "%s%s: {r: %s, g: %s, b: %s, a: %s}\n" % (
            m.group("lead"), m.group("key"), fmt(SPLASH_BG[0]), fmt(SPLASH_BG[1]), fmt(SPLASH_BG[2]), m.group("a"))
        return (new, new != line)
    r, g, b = (float(m.group(k)) for k in "rgb")
    h, s, v = colorsys.rgb_to_hsv(max(0, min(1, r)), max(0, min(1, g)), max(0, min(1, b)))
    if s < MIN_SAT or not WARM(h * 360.0):
        return line, False
    nr, ng, nb = colorsys.hsv_to_rgb(TARGET_HUE_DEG / 360.0, s, v)
    new = "%s%s: {r: %s, g: %s, b: %s, a: %s}\n" % (
        m.group("lead"), m.group("key"), fmt(nr), fmt(ng), fmt(nb), m.group("a"))
    return new, True


def process_yaml(path, dry):
    changed = 0
    out = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    nl = "\r\n" if "\r\n" in raw else "\n"
    for line in raw.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        new, did = recolor_line(stripped + "\n")
        if did:
            changed += 1
            out.append(new.rstrip("\n") + (nl if line.endswith(("\n", "\r\n")) else ""))
        else:
            out.append(line)
    if changed and not dry:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("".join(out))
    return changed


def process_sprite(path, dry):
    from PIL import Image
    im = Image.open(path)
    rgba = im.convert("RGBA")
    alpha = rgba.getchannel("A")
    hsv = rgba.convert("RGB").convert("HSV")
    h, s, v = hsv.split()
    target = int(round(TARGET_HUE_DEG / 360.0 * 255))
    tol = 10  # PIL hue units (~14 degrees): pixels already near purple are left alone, so reruns are no-ops
    sat_cut = int(MIN_SAT * 255)
    hb, sb = h.tobytes(), s.tobytes()
    mask = Image.frombytes("L", im.size, bytes(
        255 if (sv >= sat_cut and abs(hv - target) > tol) else 0 for hv, sv in zip(hb, sb)))
    new_h = Image.composite(Image.new("L", im.size, target), h, mask)
    changed = sum(1 for m in mask.tobytes() if m)
    if changed and not dry:
        rgb = Image.merge("HSV", (new_h, s, v)).convert("RGB")
        out = Image.merge("RGBA", (*rgb.split(), alpha))
        out.save(path, optimize=True)
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    os.chdir(a.root)
    if not (os.path.isdir("Assets") and os.path.isdir("ProjectSettings")):
        sys.exit("Run this from the Unity project root (needs Assets/ and ProjectSettings/).")

    total = 0
    yaml_files = (glob.glob("Assets/Scenes/*.unity") + glob.glob("Assets/Prefabs/*.prefab")
                  + ["ProjectSettings/ProjectSettings.asset"])
    for p in yaml_files:
        n = process_yaml(p, a.dry_run)
        if n:
            print("%-45s %4d colours -> purple" % (p, n))
        total += n
    try:
        import PIL  # noqa: F401
        for p in SPRITES:
            if not os.path.isfile(p):
                print("skip (missing):", p)
                continue
            n = process_sprite(p, a.dry_run)
            if n:
                print("%-45s %6d pixels -> purple" % (p, n))
            total += n
    except ImportError:
        print("Pillow not installed: sprites skipped (pip install pillow)")
    print("%s: %d changes" % ("Would change" if a.dry_run else "Changed", total))


if __name__ == "__main__":
    main()
