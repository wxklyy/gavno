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


TD = 88
MTD = 32
FLD = 12
n_td = td_size // TD

# map: method name -> string offset
# build index: for each type, its methods
pat = re.compile(r"(?i)ReportViaServer|PlayerBannedHandler|GetCheatDetector|CheatDetector|AntiCheat|Anitcheat|BanedForVoteKicking|VirtualSpace")

# first: string offsets for these names
target_offsets = set()
for m in re.finditer(rb"[A-Za-z_][A-Za-z0-9_]*", region):
    s = m.group().decode()
    if pat.fullmatch(s):
        target_offsets.add((m.start(), s))

print("target method/field names in string table:")
for o, s in sorted(target_offsets):
    print(f"  {s}")

# scan all methods: method nameIndex at mtd_off + j*MTD
n_methods = mtd_size // MTD
print(f"\ntotal methods: {n_methods}")
hits = []
for j in range(n_methods):
    nidx = struct.unpack_from("<I", data, mtd_off + j * MTD)[0]
    s = get_str(nidx)
    if s and pat.fullmatch(s):
        hits.append((j, s))

print(f"\nmethods with AC-related names: {len(hits)}")

# for each hit method, find owner type by method range
types = []
for i in range(n_td):
    b = td_off + i * TD
    ms = struct.unpack_from("<i", data, b + 40)[0]
    types.append((ms, i))
types_sorted = sorted(t for t in types if t[0] >= 0)
starts = [t[0] for t in types_sorted]

import bisect
for j, s in hits:
    # owner = type with largest ms <= j
    k = bisect.bisect_right(starts, j) - 1
    owner = types_sorted[k][1] if k >= 0 else -1
    b = td_off + owner * TD
    name = get_str(struct.unpack_from("<I", data, b)[0])
    ns = get_str(struct.unpack_from("<I", data, b + 4)[0])
    print(f"  method[{j}] {s}  ->  [{owner}] {ns}.{name}  <{image_of(owner)}>")