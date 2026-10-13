import struct, sys, re

data = open(sys.argv[1], "rb").read()
hdr = struct.unpack_from("<%dI" % (2 + 29 * 2), data, 0)
pairs = [(hdr[i], hdr[i + 1]) for i in range(2, 2 + 29 * 2, 2)]

str_off, str_size = pairs[2]
mtd_off, mtd_size = pairs[5]
param_off, param_size = pairs[10]
fld_off, fld_size = pairs[11]
td_off, td_size = pairs[19]
img_off, img_size = pairs[20]

region = data[str_off:str_off + str_size]


def get_str(o):
    end = region.find(b"\x00", o)
    return region[o:end].decode("utf-8", "replace")


# ---- images (40 bytes) ----
IMG = 40
n_img = img_size // IMG
images = []
for i in range(n_img):
    base = img_off + i * IMG
    name_index = struct.unpack_from("<I", data, base)[0]
    type_start, type_count = struct.unpack_from("<II", data, base + 8)
    images.append((get_str(name_index), type_start, type_count))

print("== IMAGES ==")
for nm, ts, tc in images:
    if nm.endswith(".dll") or nm in ("Assembly-CSharp",):
        print(f"  {nm}: types [{ts}..{ts+tc})")


def image_of(idx):
    for nm, ts, tc in images:
        if ts <= idx < ts + tc:
            return nm
    return "?"


# ---- type defs (88 bytes) ----
TD = 88
n_td = td_size // TD

pat = re.compile(r"(?i)anticheat|anitcheat|antihack|systemwatch")
print("\n== ANTICHEAT TYPES ==")
ac_types = []
for i in range(n_td):
    base = td_off + i * TD
    name_index, ns_index = struct.unpack_from("<II", data, base)
    full = f"{get_str(ns_index)}.{get_str(name_index)}"
    if pat.search(full):
        method_start = struct.unpack_from("<i", data, base + 52)[0]
        field_start = struct.unpack_from("<i", data, base + 48)[0]
        field_count = struct.unpack_from("<H", data, base + 68)[0]
        method_count = struct.unpack_from("<H", data, base + 72)[0]
        ac_types.append((i, full, field_start, field_count, method_start, method_count))

# fix counts: compute from next type with greater start
def range_fix(start, idx_starts):
    greater = [s for s in idx_starts if s > start]
    return min(greater) if greater else None

# precompute all methodStart and fieldStart
all_mstarts = sorted(struct.unpack_from("<i", data, td_off + i * TD + 52)[0] for i in range(n_td))
all_fstarts = sorted(struct.unpack_from("<i", data, td_off + i * TD + 48)[0] for i in range(n_td))

MTD = None  # Il2CppMethodDefinition size candidates: try later
FLD = 12    # Il2CppFieldDefinition v24: nameIndex, typeIndex, customAttributeIndex

for idx, full, fstart, fcount, mstart, mcount in ac_types:
    print(f"\n### type[{idx}] {full}  (image: {image_of(idx)})")
    fend = range_fix(fstart, all_fstarts)
    mend = range_fix(mstart, all_mstarts)
    print(f"    fields [{fstart}..{fend}) methods [{mstart}..{mend})")
    if fend:
        for j in range(fstart, fend):
            nidx, tidx = struct.unpack_from("<II", data, fld_off + j * FLD)
            print(f"      field: {get_str(nidx)}")
    # Il2CppMethodDefinition v24 = 40 bytes:
    # nameIndex, declaringType, returnType, parameterStart, customAttributeIndex,
    # genericContainerIndex, methodIndex, invokerIndex, delegateWrapperIndex,
    # rgctxStartIndex, rgctxCount, token, flags, iflags, slot, parameterCount
    # try MTD=40
    if mend:
        for MTD in (40, 36, 44):
            if (mend - mstart) > 0:
                # sanity: nameIndex valid
                nidx = struct.unpack_from("<I", data, mtd_off + mstart * MTD)[0]
                if nidx < str_size:
                    break
        for j in range(mstart, mend):
            nidx = struct.unpack_from("<I", data, mtd_off + j * MTD)[0]
            pstart = struct.unpack_from("<I", data, mtd_off + j * MTD + 12)[0]
            pcount = struct.unpack_from("<H", data, mtd_off + j * MTD + 38)[0]
            print(f"      method: {get_str(nidx)}  (params={pcount})")

print("\nDONE")