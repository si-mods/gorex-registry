"""Checks the asset files of a theme pack and the manifest keys that name
them: `assets`, which names the files of the pack's assets folder, and
`shaders`, whose layers name the shader sources and the images they read
(docs/DSK-012-theme-shaders.md of si-mods/gorex). Also checks the NOTICE
and license files of the pack.

GoRex applies the same caps at install and at each load, and drops what
fails them (internal/theme/assets.go, internal/theme/parse.go and
internal/theme/shaders.go of si-mods/gorex). The registry refuses a pack
that fails them, so that users get what the review saw. A check reads the
headers of the images; it decodes no pixels and compiles no shader
source.
"""

import os
import pathlib
import re
import struct

# An asset name: letters, digits, '-' and '_' (validAssetName). An asset
# file: a theme name's characters with no leading '.', not "." or ".."
# and not a "*.json" name (validAssetFile over ValidName).
NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
FILE = re.compile(r"[A-Za-z0-9._-]+")

# The caps of an asset file (internal/theme/assets.go).
MAX_ASSETS = 24           # the most names the assets key keeps
MAX_FILE = 1 << 20        # a file that no shader reads: 1 MiB
MAX_PACK = 8 << 20        # all files of a theme: 8 MiB
MAX_STILL_SIDE = 1024     # an image that no shader reads, in pixels
MAX_KAGE = 16 << 10       # a shader's source: 16 KiB
MAX_SHADER_FILE = 2 << 20  # an image that only shaders read: 2 MiB
MAX_SHADER_SIDE = 2048    # the same, in pixels
MAX_ANIM_SIDE = 512       # an animated image, in pixels
MAX_FRAMES = 64           # frames of an animated image
MAX_ANIM_DECODED = 16 << 20  # bytes of an animated image's frames
MAX_DECODED = 48 << 20    # bytes of a theme's decoded images

# The caps of the shaders key (internal/theme/shaders.go).
MAX_SHADER_IMAGES = 4
MAX_SLOT_LAYERS = 4
MAX_THEME_LAYERS = 16
MAX_FACE_SHADERS = 12

# The roles a face shader may fill (FaceRoles). The first five have a
# built-in flat color, so they need no roles.<name> entry.
BUILTIN_FACES = {
    "sideBar.activeGroupBackground", "sideBar.activeGroupTabBackground",
    "sideBar.trackBackground", "sideBar.tabHoverBackground",
    "sideBar.tabActiveBackground",
}
FACE_SLOTS = BUILTIN_FACES | {
    "titleBar.background", "sideBar.background", "paneHeader.background",
    "button.background", "dropdown.background",
    "windowControl.background", "windowControl.closeBackground",
}

PNG = b"\x89PNG\r\n\x1a\n"


def is_kage(file):
    """Reports whether file names a shader source: a .kage file."""
    return file.lower().endswith(".kage")


def valid_file(v):
    """Reports whether v may name a file of the assets folder."""
    return (FILE.fullmatch(v) is not None and v not in (".", "..")
            and not v.startswith(".")
            and not (len(v) >= 5 and v[-5:].lower() == ".json"))


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
    raise AssertionError("not a PNG or GIF file")


def check_image(b, where, max_side):
    """Checks an image's header: still images at most max_side pixels a
    side, animated ones at the animated caps."""
    fmt, w, h, frames = header(b)
    assert w > 0 and h > 0, f"{where}: empty image"
    if frames > 1:
        assert frames <= MAX_FRAMES, f"{where}: {frames} frames, more than {MAX_FRAMES}"
        assert w <= MAX_ANIM_SIDE and h <= MAX_ANIM_SIDE, f"{where}: animated image of {w}x{h} px, larger than {MAX_ANIM_SIDE}"
        assert w * h * 4 * frames <= MAX_ANIM_DECODED, f"{where}: animated image of more than 16 MiB decoded"
    else:
        assert w <= max_side and h <= max_side, f"{where}: image of {w}x{h} px, larger than {max_side}"
    return w, h


def slot_layers(slot, api, files):
    """Returns the (source, images) pairs of a shader slot as GoRex parses
    them, or None when the slot drops: a layer needs a .kage asset as its
    source and image assets as its images."""
    if api == 2 and isinstance(slot, list):
        if not 1 <= len(slot) <= MAX_SLOT_LAYERS:
            return None
        layers = slot
    else:
        layers = [slot]
    out = []
    for layer in layers:
        if not isinstance(layer, dict):
            return None
        src = layer.get("source")
        if not isinstance(src, str) or src not in files or not is_kage(files[src]):
            return None
        names = layer.get("images")
        if names is None:
            names = []
        if not isinstance(names, list):
            return None
        names = names[:MAX_SHADER_IMAGES]
        for n in names:
            if not isinstance(n, str) or n not in files or is_kage(files[n]):
                return None
        out.append((src, names))
    return out


def shader_uses(data, files):
    """Returns (sources, images): the asset names the shaders key of data
    reads, as the layers of a parsed manifest give them (GoRex's
    Manifest.uses). A slot GoRex drops reads nothing."""
    sources, images = set(), set()
    sh = data.get("shaders")
    if not isinstance(sh, dict):
        return sources, images
    api = sh.get("api")
    if isinstance(api, bool) or api not in (1, 2):
        return sources, images
    slots = []
    if "background" in sh:
        slots.append(slot_layers(sh["background"], api, files))
    faces = sh.get("faces")
    if isinstance(faces, dict):
        roles = data.get("roles")
        roles = roles if isinstance(roles, dict) else {}
        kept = 0
        for role in sorted(faces):
            if role not in FACE_SLOTS or kept == MAX_FACE_SHADERS:
                continue
            if role not in BUILTIN_FACES:
                v = roles.get(role)
                if not (isinstance(v, str) or isinstance(v, dict) and {"light", "dark"} <= set(v)):
                    continue  # a face shader needs the role's flat color
            layers = slot_layers(faces[role], api, files)
            if layers is not None:
                slots.append(layers)
                kept += 1
    used = 0
    for layers in slots:
        if layers is None or used + len(layers) > MAX_THEME_LAYERS:
            continue
        used += len(layers)
        for src, names in layers:
            sources.add(src)
            images.update(names)
    return sources, images


def check(data, root, where):
    """Checks the asset keys of the manifest data of the pack at root."""
    root = pathlib.Path(root)
    # No link anywhere in the pack: not the assets folder, the NOTICE or a
    # license file, nor any other file. A link could point out of the pack.
    for top, dirs, files_ in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d != ".git" or pathlib.Path(top) != root]
        for name in dirs + files_:
            assert not os.path.islink(os.path.join(top, name)), f"{where}: {os.path.relpath(os.path.join(top, name), root)} is a link"
    assets = data.get("assets", {})
    assert isinstance(assets, dict), f"{where}: assets is not an object"
    assert len(assets) <= MAX_ASSETS, f"{where}: more than {MAX_ASSETS} assets"
    files = {}
    for name, v in assets.items():
        w = f"{where}: assets.{name}"
        assert NAME.fullmatch(name), f"{w}: bad name"
        assert isinstance(v, str) and valid_file(v), f"{w}: bad file name {v!r}"
        files[name] = v
    _, images = shader_uses(data, files)
    total = decoded = 0
    seen = set()
    for name, f in files.items():
        p = root / "assets" / f
        w = f"{where}: assets.{name} ({f})"
        assert p.is_file() and not p.is_symlink(), f"{w}: missing, or not a regular file"
        size = p.stat().st_size
        if is_kage(f):
            limit = MAX_KAGE
        elif name in images:
            limit = MAX_SHADER_FILE
        else:
            limit = MAX_FILE
        assert size <= limit, f"{w}: larger than {limit >> 10} KiB"
        if f not in seen:
            seen.add(f)
            total += size
        b = p.read_bytes()
        if is_kage(f):
            # A .kage file is UTF-8 text with no NUL byte (checkKage);
            # GoRex compiles it at load, which this check does not try.
            try:
                b.decode("utf-8")
            except UnicodeDecodeError:
                raise AssertionError(f"{w}: a .kage file is not UTF-8 text")
            assert b"\x00" not in b, f"{w}: a .kage file is not UTF-8 text"
        else:
            max_side = MAX_SHADER_SIDE if name in images else MAX_STILL_SIDE
            iw, ih = check_image(b, w, max_side)
            if name in images:
                decoded += iw * ih * 4
                assert decoded <= MAX_DECODED, f"{where}: the theme's images pass {MAX_DECODED >> 20} MiB decoded"
    assert total <= MAX_PACK, f"{where}: assets larger than {MAX_PACK >> 20} MiB"

    if files:
        notice = root / "NOTICE"
        assert notice.is_file(), f"{where}: a pack with assets has no NOTICE"
        for name in sorted(set(re.findall(r"\bLICENSE[A-Za-z0-9._-]*", notice.read_text(encoding="utf-8")))):
            name = name.rstrip(".")
            assert (root / name).is_file(), f"{where}: NOTICE names {name}, which the pack does not have"
