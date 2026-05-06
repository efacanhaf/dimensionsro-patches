"""Build 0007.thor: ship the booster pack iteminfo edits, the 3 VIP
ticket entries (with VIP_Black_Card sprite) and the ItemMoveInfoV5.txt
whitelist update so the client renders all 9 trade restrictions on
hover for the VIP tickets.

THOR header layout (50 bytes):
  magic         = b'ASSF (C) 2007 Aeomin DEV'    (24)
  use_grf       = 0x01                          (1)
  file_count    = int32 LE                      (4)
  mode          = 0x0030                        (2)
  tname_len     = 1 byte                        (1)
  tname         = b'server.grf'                 (10)
  ftbl_csize    = int32 LE                      (4)
  ftbl_offset   = int32 LE                      (4)
"""
from __future__ import annotations
import struct
import zlib
from pathlib import Path

PATCHES_DIR = Path(r"C:\Users\Eduardo\Documents\dev\dimensionsro-patches\patches")
OUT = PATCHES_DIR / "0007.thor"

# Sources are taken from the canonical kRO data tree on disk + the GRF.
# We intentionally pull from server.grf (canonical) so the THOR matches
# what we deployed locally.
import sys
sys.path.insert(0, r"C:\Users\Eduardo\Documents\dev\.work-novfemale-rebuild")
import grf_lib  # type: ignore

GRF = r"C:\RO-dev\server.grf"

WANTED = [
    b"data\\luafiles514\\lua files\\datainfo\\iteminfo.lub",
    b"data\\luafiles514\\lua files\\datainfo\\iteminfo_true.lub",
    b"data\\ItemMoveInfoV5.txt",
]


def main() -> int:
    print(f"reading source GRF {GRF} ...")
    entries = grf_lib.read_grf(GRF)
    bodies: list[tuple[bytes, bytes]] = []   # (gname, raw uncompressed)
    for w in WANTED:
        if w not in entries:
            raise SystemExit(f"missing in GRF: {w.decode('latin-1')}")
        raw = grf_lib.get_file(entries, w)
        bodies.append((w, raw))
        print(f"  + {w.decode('latin-1')}: {len(raw):,} bytes")

    # data.integrity is a manifest of CRC32s, one per filename.
    integrity_lines = [
        f"{name.decode('latin-1')}=0x{zlib.crc32(raw) & 0xffffffff:08x}\r\n"
        for name, raw in bodies
    ]
    integrity = "".join(integrity_lines).encode("ascii")
    bodies.append((b"data.integrity", integrity))
    print(f"  + data.integrity: {len(integrity)} bytes")

    # Compress every body, lay them out, build the entry table, then header.
    compressed_bodies: list[tuple[bytes, bytes, int]] = []  # (gname, comp, usize)
    for name, raw in bodies:
        c = zlib.compress(raw, 6)
        compressed_bodies.append((name, c, len(raw)))

    magic = b"ASSF (C) 2007 Aeomin DEV"
    use_grf = bytes([1])
    file_count = struct.pack("<i", len(compressed_bodies))
    mode = struct.pack("<H", 0x30)
    target_name = b"server.grf"
    target_name_len = bytes([len(target_name)])
    header_size = 24 + 1 + 4 + 2 + 1 + len(target_name) + 4 + 4
    assert header_size == 50

    cur = header_size
    placed: list[tuple[bytes, bytes, int, int, int]] = []  # (name, comp, off, csize, usize)
    for name, comp, usize in compressed_bodies:
        placed.append((name, comp, cur, len(comp), usize))
        cur += len(comp)

    # Build entry table (uncompressed): for each entry,
    #   1 byte name_len, name (latin-1), 1 byte flag, int32 offset, int32 csize, int32 usize.
    tbl = b""
    for name, _comp, off, csize, usize in placed:
        nb = name  # already bytes
        tbl += bytes([len(nb)]) + nb + bytes([0])
        tbl += struct.pack("<iii", off, csize, usize)

    tbl_compressed = zlib.compress(tbl, 6)
    ftbl_csize = len(tbl_compressed)
    ftbl_offset = cur

    header = (
        magic + use_grf + file_count + mode + target_name_len + target_name
        + struct.pack("<i", ftbl_csize) + struct.pack("<i", ftbl_offset)
    )
    assert len(header) == 50

    blob = header
    for _name, comp, _off, _cs, _us in placed:
        blob += comp
    blob += tbl_compressed

    OUT.write_bytes(blob)
    print(f"\nwrote {OUT}: {len(blob):,} bytes")

    # Round-trip verify
    d = OUT.read_bytes()
    assert d[:24] == magic
    v_count = struct.unpack_from("<i", d, 25)[0]
    v_mode = struct.unpack_from("<H", d, 29)[0]
    v_tnl = d[31]
    v_tn = d[32:32 + v_tnl]
    v_ftbl_csize = struct.unpack_from("<i", d, 32 + v_tnl)[0]
    v_ftbl_off = struct.unpack_from("<i", d, 32 + v_tnl + 4)[0]
    assert v_count == len(compressed_bodies)
    assert v_mode == 0x30
    assert v_tn == target_name
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
