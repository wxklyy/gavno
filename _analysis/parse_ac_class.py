import struct, sys

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
        return f"<bad:{o}>"
    end = region.find(b"\x00", o)
    return region[o:end].decode("utf-8", "replace")


# images (40b) -> find Assembly-CSharp range
IMG = 40
n_img = img_size // IMG
cs_range = None
for i in range(n_img):
    base = img_off + i * IMG
    name = get_str(struct.unpack_from("<I", data, base)[0])
    ts, tc = struct.unpack_from("<II", data, base + 8)
    if name == "Assembly-CSharp.dll":
        cs_range = (ts, ts + tc)
    if name == "Assembly-CSharp-firstpass.dll":
        fp_range = (ts, ts + tc)

print("Assembly-CSharp range:", cs_range)

TD = 88
n_td = td_size // TD

# dump raw ints of the AC class record
ac_idx = 12236
base = td_off + ac_idx * TD
vals = struct.unpack_from("<22i", data, base)
print("\nAntiCheatManager raw record ints:")
for i, v in enumerate(vals):
    print(f"  [{i*4:02d}] {v}")
print("name:", get_str(vals[0]), " ns:", get_str(vals[1]))

# Heuristic: in Il2CppTypeDefinition v24 the layout is:
# 0 nameIndex, 1 namespaceIndex, 2 byvalTypeIndex, 3 byrefTypeIndex,
# 4 declaringTypeIndex, 5 parentIndex, 6 elementTypeIndex, 7 genericContainerIndex,
# 8 flags, 9 fieldStart, 10 methodStart, 11 eventStart, 12 propertyStart,
# 13 nestedTypesStart, 14 interfacesStart, 15 vtableStart, 16 interfaceOffsetsStart,
# 17 method_count, 18 property_count, 19 field_count, 20 event_count,
# 21 nested_type_count, ...
# Try ints instead of shorts for counts
field_start = vals[9]
method_start = vals[10]
print("\nfield_start:", field_start, "method_start:", method_start)

# next type's starts
def next_start(cur, pos):
    best = None
    for i in range(n_td):
        v = struct.unpack_from("<i", data, td_off + i * TD + pos)[0]
        if v > cur and (best is None or v < best):
            best = v
    return best

fend = next_start(field_start, 9 * 4)
mend = next_start(method_start, 10 * 4)
print("field range:", field_start, "..", fend, " method range:", method_start, "..", mend)

FLD = 12
if fend and fend - field_start < 200:
    print("\n== FIELDS ==")
    for j in range(field_start, fend):
        nidx, tidx, caidx = struct.unpack_from("<III", data, fld_off + j * FLD)
        print(f"  [{j}] {get_str(nidx)}  (typeIndex={tidx})")

# Method def: try sizes 40
for MTD in (40,):
    print(f"\n== METHODS (MTD={MTD}) ==")
    if mend and 0 < mend - method_start < 200:
        for j in range(method_start, mend):
            nidx = struct.unpack_from("<I", data, mtd_off + j * MTD)[0]
            print(f"  [{j}] {get_str(nidx)}")

# Also: enumerate ALL types in Assembly-CSharp whose ns contains 'nitcheat' (case-insens) or name contains cheat/watch/guard
print("\n== ALL types with cheat-ish names in Assembly-CSharp ==")
import re
pat = re.compile(r"(?i)cheat|watch|guard|shield|hack|detect")
for i in range(cs_range[0], cs_range[1]):
    b = td_off + i * TD
    name = get_str(struct.unpack_from("<I", data, b)[0])
    ns = get_str(struct.unpack_from("<I", data, b + 4)[0])
    if pat.search(name) or pat.search(ns):
        print(f"  [{i}] {ns}.{name}")