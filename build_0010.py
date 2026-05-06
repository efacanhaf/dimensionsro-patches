"""Build 0010.thor: re-ship the 0008 baseline of System/LuaFiles514/itemInfo.lub
+ SystemEN/LuaFiles514/itemInfo.lua to override the broken 0009 content
on clients that already pulled it.

THOR 0009 was built from C:\\Users\\Eduardo\\Documents\\dev\\.dro-build\\
iteminfo_dro_text.lua, which had divergent content (different size, possibly
broken). User reports clients with 0009 are showing corruption. Rolling
plist back to 8 stops new clients from pulling 0009, but clients already
on patch_index >= 9 won't re-pull anything older. This patch (0010) ships
the LAST GOOD version of the loose iteminfo files (extracted from
patches/0008.thor) so those affected clients overwrite the broken 0009
state with the working 0008-era bytes.

The "Max Base Level 10" text is back in the descriptions because that's
the state at 0008. That's intentional -- prefer the working baseline over
the broken edit. We can re-ship a clean description fix later if needed.

Loose-mode template (use_grf=0, empty target_grf_name) -- same as 0008/0009.
"""
from __future__ import annotations
import struct
import zlib
from pathlib import Path

PATCHES_DIR = Path(r"C:\Users\Eduardo\Documents\dev\dimensionsro-patches\patches")
OUT = PATCHES_DIR / "0010.thor"

# Source: bytes extracted from patches/0008.thor (the last known good state).
# After extraction these were also restored to C:\RO-dev so the dev tree
# matches the shipped state.
SOURCES: list[tuple[bytes, Path]] = [
    (
        rb"System\LuaFiles514\itemInfo.lub",
        Path(r"C:\RO-dev\System\LuaFiles514\itemInfo.lub"),
    ),
    (
        rb"SystemEN\LuaFiles514\itemInfo.lua",
        Path(r"C:\RO-dev\SystemEN\LuaFiles514\itemInfo.lua"),
    ),
]


def main() -> int:
    bodies: list[tuple[bytes, bytes]] = []
    for entry_name, src_path in SOURCES:
        if not src_path.exists():
            raise SystemExit(f"missing source: {src_path}")
        raw = src_path.read_bytes()
        bodies.append((entry_name, raw))
        print(f"  + {entry_name.decode('latin-1')}: {len(raw):,} bytes  (from {src_path})")

    compressed_bodies: list[tuple[bytes, bytes, int]] = []
    for name, raw in bodies:
        c = zlib.compress(raw, 6)
        compressed_bodies.append((name, c, len(raw)))

    magic = b"ASSF (C) 2007 Aeomin DEV"
    use_grf = bytes([0])
    file_count = struct.pack("<i", len(compressed_bodies))
    mode = struct.pack("<H", 0x30)
    target_name = b""
    target_name_len = bytes([0])
    header_size = 24 + 1 + 4 + 2 + 1 + 0 + 4 + 4
    assert header_size == 40

    cur = header_size
    placed: list[tuple[bytes, bytes, int, int, int]] = []
    for name, comp, usize in compressed_bodies:
        placed.append((name, comp, cur, len(comp), usize))
        cur += len(comp)

    tbl = b""
    for name, _comp, off, csize, usize in placed:
        tbl += bytes([len(name)]) + name + bytes([0])
        tbl += struct.pack("<iii", off, csize, usize)

    tbl_compressed = zlib.compress(tbl, 6)
    ftbl_csize = len(tbl_compressed)
    ftbl_offset = cur

    header = (
        magic + use_grf + file_count + mode + target_name_len + target_name
        + struct.pack("<i", ftbl_csize) + struct.pack("<i", ftbl_offset)
    )
    assert len(header) == header_size

    blob = header
    for _name, comp, _off, _cs, _us in placed:
        blob += comp
    blob += tbl_compressed

    OUT.write_bytes(blob)
    print(f"\nwrote {OUT}: {len(blob):,} bytes")

    d = OUT.read_bytes()
    assert d[:24] == magic
    assert d[24] == 0
    v_count = struct.unpack_from("<i", d, 25)[0]
    v_tnl = d[31]
    assert v_tnl == 0
    v_ftbl_csize = struct.unpack_from("<i", d, 32)[0]
    v_ftbl_off = struct.unpack_from("<i", d, 36)[0]
    assert v_count == len(compressed_bodies)
    raw_tbl = zlib.decompress(d[v_ftbl_off:v_ftbl_off + v_ftbl_csize])
    off = 0
    for _ in range(v_count):
        nl = raw_tbl[off]; off += 1
        nm = raw_tbl[off:off + nl]; off += nl
        _flag = raw_tbl[off]; off += 1
        eo = struct.unpack_from("<i", raw_tbl, off)[0]; off += 4
        cs = struct.unpack_from("<i", raw_tbl, off)[0]; off += 4
        us = struct.unpack_from("<i", raw_tbl, off)[0]; off += 4
        content = zlib.decompress(d[eo:eo + cs])
        assert len(content) == us
        print(f"  verify {nm.decode('latin-1')}: {us:,} bytes OK")
    print("verify complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
