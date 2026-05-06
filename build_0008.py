"""Build 0008.thor: ship the loose-file iteminfo (the one Ragexe actually
reads).

Discovery during 0007 deploy: this DimensionsRO Ragexe build is hexed to
read item names/descriptions from `System\\LuaFiles514\\itemInfo.lub`
(loose file on disk), NOT from `data\\luafiles514\\lua files\\datainfo\\
iteminfo.lub` inside the GRF. THOR 0007 patched the GRF entry but the
client never opens that path -- result: VIP tickets (1270142+) showed as
"Unknown Item" in prod even though the GRF had the right data.

Fix: ship the loose copies via THOR with `use_grf=0` so rpatchur writes
them directly to the install root.

Two paths are shipped because the Korean langtype branch reads from
`System\\LuaFiles514\\itemInfo.lub` (compiled .lub) and the English
branch reads from `SystemEN\\LuaFiles514\\itemInfo.lua` (Lua text). In
the dev tree they are byte-identical (same md5) -- just different paths
the Ragexe variants look up.

THOR header layout (40 bytes, no target_grf_name -> tname_len=0):
  magic         = b'ASSF (C) 2007 Aeomin DEV'    (24)
  use_grf       = 0x00                          (1)   # loose mode
  file_count    = int32 LE                      (4)
  mode          = 0x0030                        (2)
  tname_len     = 0                             (1)
  tname         = (empty)                       (0)
  ftbl_csize    = int32 LE                      (4)
  ftbl_offset   = int32 LE                      (4)
"""
from __future__ import annotations
import struct
import zlib
from pathlib import Path

PATCHES_DIR = Path(r"C:\Users\Eduardo\Documents\dev\dimensionsro-patches\patches")
OUT = PATCHES_DIR / "0008.thor"

# Source: loose files on the dev install. They're maintained outside the
# GRF and that's the canonical location for this client build.
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

    # Compress every body, lay them out, build the entry table, then header.
    compressed_bodies: list[tuple[bytes, bytes, int]] = []
    for name, raw in bodies:
        c = zlib.compress(raw, 6)
        compressed_bodies.append((name, c, len(raw)))

    magic = b"ASSF (C) 2007 Aeomin DEV"
    use_grf = bytes([0])  # loose-file mode
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

    # Round-trip verify.
    d = OUT.read_bytes()
    assert d[:24] == magic
    assert d[24] == 0  # use_grf=0
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
