"""Checks the keys of a theme pack that GoRex's docs/DSK-010-theme-ambience.md
adds: assets, ambience, mascot, brand and ticker, against the caps of its
Caps table, and the asset files and license files of the pack.

GoRex applies the same caps at install and at each load, and drops what
fails. The registry refuses a pack that fails them, so that users get what
the review saw. A check reads the headers of the images; it decodes no
pixels.
"""

import pathlib
import re
import struct

NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
FILE = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
HEX = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
ANCHORS = {"topLeft", "topRight", "bottomLeft", "bottomRight", "center"}

MAX_FILE = 1 << 20
MAX_PACK = 4 << 20
MAX_STILL_SIDE = 1024
MAX_ANIM_SIDE = 512
MAX_FRAMES = 64
MAX_ANIM_DECODED = 16 << 20
PNG = b"\x89PNG\r\n\x1a\n"


def header(b):
    """Returns (format, width, height, frames) from an image's header."""
    if b.startswith(PNG):
        assert b[12:16] == b"IHDR", "PNG without IHDR"
        w, h = struct.unpack(">II", b[16:24])
        i, frames, fmt = 8, 1, "png"
        while i + 12 <= len(b):
            n = struct.unpack(">I", b[i:i + 4])[0]
            typ = b[i + 4:i + 8]
            if typ == b"IDAT":
                break
            if typ == b"acTL":
                frames, fmt = struct.unpack(">I", b[i + 8:i + 12])[0], "apng"
                break
            i += 12 + n
        return fmt, w, h, frames
    if b[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", b[6:10])
        i = 13 + (3 << ((b[10] & 7) + 1) if b[10] & 0x80 else 0)
        frames = 0

        def skip(i):
            while True:
                n = b[i]
                i += 1 + n
                if n == 0:
                    return i

        while i < len(b) and b[i] != 0x3B:
            if b[i] == 0x21:
                i = skip(i + 2)
            elif b[i] == 0x2C:
                flags = b[i + 9]
                i += 10 + (3 << ((flags & 7) + 1) if flags & 0x80 else 0) + 1
                i = skip(i)
                frames += 1
                assert frames <= MAX_FRAMES, f"GIF of more than {MAX_FRAMES} frames"
            else:
                raise AssertionError("bad GIF block")
        assert frames > 0, "GIF without an image"
        return "gif", w, h, frames
    head = b[:1024].lstrip(b"\xef\xbb\xbf").lstrip()
    if head.startswith(b"<") and b"<svg" in head:
        return "svg", 0, 0, 1
    raise AssertionError("not a PNG, GIF or SVG file")


def check_image(b, where):
    fmt, w, h, frames = header(b)
    if fmt == "svg":
        return fmt
    assert w > 0 and h > 0, f"{where}: empty image"
    if frames > 1:
        assert frames <= MAX_FRAMES, f"{where}: {frames} frames, more than {MAX_FRAMES}"
        assert w <= MAX_ANIM_SIDE and h <= MAX_ANIM_SIDE, f"{where}: animated image of {w}x{h} px, larger than {MAX_ANIM_SIDE}"
        assert w * h * 4 * frames <= MAX_ANIM_DECODED, f"{where}: animated image of more than 16 MiB decoded"
    else:
        assert w <= MAX_STILL_SIDE and h <= MAX_STILL_SIDE, f"{where}: image of {w}x{h} px, larger than {MAX_STILL_SIDE}"
    return fmt


def color(v, where, max_alpha=None):
    vals = [v] if not isinstance(v, dict) else [v.get("light"), v.get("dark")]
    if isinstance(v, dict):
        assert set(v) == {"light", "dark"}, f"{where}: want light and dark"
    for c in vals:
        assert isinstance(c, str) and HEX.match(c), f"{where}: bad color {c!r}"
        if max_alpha is not None and len(c) in (5, 9):
            a = int(c[4] * 2, 16) if len(c) == 5 else int(c[7:9], 16)
            assert a <= round(max_alpha * 255), f"{where}: alpha above {max_alpha}"


def num(o, key, where, lo, hi, required=False):
    if key not in o:
        assert not required, f"{where}: missing {key}"
        return
    v = o[key]
    assert isinstance(v, (int, float)) and not isinstance(v, bool), f"{where}.{key}: not a number"
    assert lo <= v <= hi, f"{where}.{key}: {v} outside {lo} to {hi}"


def text(s, where, n):
    assert isinstance(s, str), f"{where}: not a string"
    assert len(s) <= n, f"{where}: more than {n} characters"
    bad = [c for c in s if ord(c) < 0x20 or 0x7F <= ord(c) < 0xA0 or ord(c) in (0x61C, 0x200E, 0x200F)
           or 0x202A <= ord(c) <= 0x202E or 0x2066 <= ord(c) <= 0x2069]
    assert not bad, f"{where}: control or bidirectional characters"


def keys(o, where, known):
    assert isinstance(o, dict), f"{where}: not an object"
    assert set(o) <= known, f"{where}: unknown keys {sorted(set(o) - known)}"


def check(data, root, where):
    """Checks the DSK-010 keys of the manifest data of the pack at root."""
    root = pathlib.Path(root)
    assets = data.get("assets", {})
    keys(assets, f"{where}: assets", set(assets))
    assert len(assets) <= 16, f"{where}: more than 16 assets"
    files, sheets, formats = {}, set(), {}
    for name, v in assets.items():
        w = f"{where}: assets.{name}"
        assert NAME.fullmatch(name), f"{w}: bad name"
        if isinstance(v, dict):
            keys(v, w, {"file", "frames", "columns", "fps"})
            num(v, "frames", w, 1, MAX_FRAMES, required=True)
            num(v, "columns", w, 1, MAX_FRAMES)
            num(v, "fps", w, 1, 30)
            sheets.add(name)
            v = v.get("file")
        assert isinstance(v, str) and FILE.fullmatch(v) and v not in (".", ".."), f"{w}: bad file name {v!r}"
        files[name] = v
    total = 0
    for name, f in files.items():
        p = root / "assets" / f
        w = f"{where}: assets.{name} ({f})"
        assert p.is_file() and not p.is_symlink(), f"{w}: missing, or not a regular file"
        size = p.stat().st_size
        assert size <= MAX_FILE, f"{w}: larger than 1 MiB"
        total += size
        formats[name] = check_image(p.read_bytes(), w)
        assert not (name in sheets and formats[name] == "svg"), f"{w}: a sprite sheet is not an SVG"
    assert total <= MAX_PACK, f"{where}: assets larger than 4 MiB"

    def image(name, w, svg=False):
        assert name in files, f"{w}: no asset {name!r}"
        assert svg or formats[name] != "svg", f"{w}: an SVG is only for brand.icon"

    amb = data.get("ambience", {})
    keys(amb, f"{where}: ambience", {"glows", "images", "particles", "sprites"})
    glows = amb.get("glows", [])
    assert isinstance(glows, list) and len(glows) <= 4, f"{where}: ambience.glows: at most 4"
    for i, g in enumerate(glows):
        w = f"{where}: ambience.glows[{i}]"
        keys(g, w, {"x", "y", "rx", "ry", "color"})
        for k in ("x", "y"):
            num(g, k, w, -0.5, 1.5)
        for k in ("rx", "ry"):
            num(g, k, w, 0.05, 1.5)
        color(g.get("color"), f"{w}.color", max_alpha=0.4)
    images = amb.get("images", [])
    assert isinstance(images, list) and len(images) <= 2, f"{where}: ambience.images: at most 2"
    for i, im in enumerate(images):
        w = f"{where}: ambience.images[{i}]"
        keys(im, w, {"asset", "anchor", "height", "opacity"})
        image(im.get("asset"), w)
        assert im.get("asset") not in sheets, f"{w}: a sprite sheet is not a still image"
        assert im.get("anchor", "bottomRight") in ANCHORS, f"{w}: bad anchor"
        num(im, "height", w, 0.05, 1024)
        num(im, "opacity", w, 0, 0.25)
    particles = amb.get("particles", [])
    assert isinstance(particles, list) and len(particles) <= 2, f"{where}: ambience.particles: at most 2 layers"
    count = 0
    for i, pt in enumerate(particles):
        w = f"{where}: ambience.particles[{i}]"
        keys(pt, w, {"shape", "count", "size", "seconds", "color"})
        assert pt.get("shape") == "bubble", f"{w}: bad shape"
        num(pt, "count", w, 1, 40, required=True)
        count += pt["count"]
        for k, lo, hi in (("size", 2, 32), ("seconds", 4, 120)):
            r = pt.get(k, [lo, lo])
            assert isinstance(r, list) and len(r) == 2 and all(isinstance(x, (int, float)) and lo <= x <= hi for x in r), f"{w}.{k}: want two numbers from {lo} to {hi}"
        if "color" in pt:
            color(pt["color"], f"{w}.color", max_alpha=0.6)
    assert count <= 40, f"{where}: more than 40 particles"
    sprites = amb.get("sprites", [])
    assert isinstance(sprites, list) and len(sprites) <= 8, f"{where}: ambience.sprites: at most 8"
    for i, sp in enumerate(sprites):
        w = f"{where}: ambience.sprites[{i}]"
        keys(sp, w, {"asset", "y", "height", "seconds", "direction", "opacity", "mirror"})
        image(sp.get("asset"), w)
        num(sp, "y", w, 0, 1)
        num(sp, "height", w, 16, 200)
        num(sp, "seconds", w, 8, 600)
        num(sp, "opacity", w, 0, 0.3)
        assert sp.get("direction", "right") in ("left", "right", "up"), f"{w}: bad direction"
        assert isinstance(sp.get("mirror", True), bool), f"{w}.mirror: not a boolean"

    mascot = data.get("mascot")
    if mascot is not None:
        w = f"{where}: mascot"
        keys(mascot, w, {"idle", "active", "height", "caption", "quotes", "popup"})
        for k in ("idle", "active", "popup"):
            if k in mascot:
                image(mascot[k], f"{w}.{k}")
        num(mascot, "height", w, 48, 128)
        if "caption" in mascot:
            text(mascot["caption"], f"{w}.caption", 24)
        quotes = mascot.get("quotes", [])
        assert isinstance(quotes, list) and len(quotes) <= 32, f"{w}.quotes: at most 32"
        for i, q in enumerate(quotes):
            text(q, f"{w}.quotes[{i}]", 80)

    brand = data.get("brand")
    if brand is not None:
        w = f"{where}: brand"
        keys(brand, w, {"icon", "wordmark"})
        if "icon" in brand:
            image(brand["icon"], f"{w}.icon", svg=True)
            assert brand["icon"] not in sheets, f"{w}.icon: a sprite sheet is not an icon"
        if "wordmark" in brand:
            text(brand["wordmark"], f"{w}.wordmark", 24)

    ticker = data.get("ticker")
    if ticker is not None:
        w = f"{where}: ticker"
        keys(ticker, w, {"lines", "seconds"})
        lines = ticker.get("lines", [])
        assert isinstance(lines, list) and len(lines) <= 32, f"{w}.lines: at most 32"
        for i, line in enumerate(lines):
            text(line, f"{w}.lines[{i}]", 80)
        num(ticker, "seconds", w, 6, 120)

    if files:
        notice = root / "NOTICE"
        assert notice.is_file(), f"{where}: a pack with assets has no NOTICE"
        for name in sorted(set(re.findall(r"\bLICENSE[A-Za-z0-9._-]*", notice.read_text(encoding="utf-8")))):
            name = name.rstrip(".")
            assert (root / name).is_file(), f"{where}: NOTICE names {name}, which the pack does not have"
