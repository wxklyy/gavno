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
n_img = img_size // IMG
images = []
for i in range(n_img):
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

# precompute sorted lists of all method/field starts for range derivation
all_mstarts = sorted(set(struct.unpack_from("<i", data, td_off + i * TD + 40)[0] for i in range(n_td) if struct.unpack_from("<i", data, td_off + i * TD + 40)[0] >= 0))
all_fstarts = sorted(set(struct.unpack_from("<i", data, td_off + i * TD + 36)[0] for i in range(n_td) if struct.unpack_from("<i", data, td_off + i * TD + 36)[0] >= 0))


def upper_bound(lst, x):
    lo, hi = 0, len(lst)
    while lo < hi:
        mid = (lo + hi) // 2
        if lst[mid] <= x:
            lo = mid + 1
        else:
            hi = mid
    return lst[lo] if lo < len(lst) else None


def dump_type(i, max_methods=60, max_fields=60):
    b = td_off + i * TD
    name = get_str(struct.unpack_from("<I", data, b)[0])
    ns = get_str(struct.unpack_from("<I", data, b + 4)[0])
    field_start, method_start = struct.unpack_from("<ii", data, b + 36)
    fend = upper_bound(all_fstarts, field_start) if field_start >= 0 else None
    mend = upper_bound(all_mstarts, method_start) if method_start >= 0 else None
    img = image_of(i)
    print(f"\n### [{i}] {ns}.{name}   <{img}>")
    if field_start >= 0 and fend:
        n = fend - field_start
        print(f"    fields ({n}):")
        for j in range(field_start, min(fend, field_start + max_fields)):
            nidx, tidx = struct.unpack_from("<II", data, fld_off + j * FLD)
            print(f"      {get_str(nidx)}")
    if method_start >= 0 and mend:
        n = mend - method_start
        print(f"    methods ({n}):")
        for j in range(method_start, min(mend, method_start + max_methods)):
            nidx = struct.unpack_from("<I", data, mtd_off + j * MTD)[0]
            print(f"      {get_str(nidx)}")


targets = {}
for i in range(n_td):
    b = td_off + i * TD
    name = get_str(struct.unpack_from("<I", data, b)[0]) or ""
    ns = get_str(struct.unpack_from("<I", data, b + 4)[0]) or ""
    full = f"{ns}.{name}"
    if name in ("GameAntiCheatManager", "AntiCheatManager", "ColliderAnit\u0421heat2", "Observer", "AnitcheatTesting") or \
       "Anticheat" in ns or "Anitcheat" in ns or "SystemWatch" in full:
        targets[i] = full

print("targets:", {i: t for i, t in targets.items()})
for i in sorted(targets):
    dump_type(i)