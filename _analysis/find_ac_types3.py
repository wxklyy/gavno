import struct, sys, re

data = open(sys.argv[1], "rb").read()
hdr = struct.unpack_from("<%dI" % (2 + 29 * 2), data, 0)
pairs = [(hdr[i], hdr[i + 1]) for i in range(2, 2 + 29 * 2, 2)]

str_off, str_size = pairs[2]
mtd_off, mtd_size = pairs[5]
fld_off, fld_size = pairs[11]
td_off, td_size = pairs[19]
img_off, img_size = pairs[20]

region = data[str_off:str_off + str_size]


def get_str(o):
    if o < 0 or o >= str_size:
        return None
    end = region.find(b"\x00", o)
    return region[o:end].decode("utf-8", "replace")


IMG = 40
images = []
for i in range(img_size // IMG):
    base = img_off + i * IMG
    name = get_str(struct.unpack_from("<I", data, base)[0])
    ts, tc = struct.unpack_from("<II", data, base + 8)
    images.append((name, ts, ts + tc))


def image_of(idx):
    for nm, s, e in images:
        if s <= idx < e:
            return nm
    return "?"


# string table offsets of interesting names
targets = {
    1181505: "GameAntiCheatManager",
    1181380: "ColliderAnitСheat2",
    1217869: "Observer",
    978885: "AnitcheatTesting",
}

# scan whole metadata for these offsets as little-endian u32
print("== occurrences of name offsets in typeDefinitions region ==")
for o, nm in targets.items():
    needle = struct.pack("<I", o)
    start = td_off
    end = td_off + td_size
    hits = []
    cur = start
    while True:
        p = data.find(needle, cur, end)
        if p == -1:
            break
        rel = (p - td_off)
        if rel % 88 == 0:
            idx = rel // 88
            hits.append((idx, p))
        cur = p + 1
    print(f"  {nm} (off={o}): typedef-index hits -> {hits}")

# Also scan full file to see where these offsets are referenced
print("\n== occurrences anywhere ==")
for o, nm in targets.items():
    needle = struct.pack("<I", o)
    hits = []
    cur = 0
    while True:
        p = data.find(needle, cur)
        if p == -1:
            break
        hits.append(p)
        cur = p + 1
        if len(hits) > 20:
            break
    print(f"  {nm}: {len(hits)} hits at {[hex(h) for h in hits[:20]]}")