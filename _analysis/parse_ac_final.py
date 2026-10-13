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
        return f"<bad:{o}>"
    end = region.find(b"\x00", o)
    return region[o:end].decode("utf-8", "replace")


IMG = 40
n_img = img_size // IMG
ranges = {}
for i in range(n_img):
    base = img_off + i * IMG
    name = get_str(struct.unpack_from("<I", data, base)[0])
    ts, tc = struct.unpack_from("<II", data, base + 8)
    ranges[name] = (ts, ts + tc)

TD = 88
n_td = td_size // TD
MTD = 40
FLD = 12


def dump_type(i):
    b = td_off + i * TD
    name = get_str(struct.unpack_from("<I", data, b)[0])
    ns = get_str(struct.unpack_from("<I", data, b + 4)[0])
    field_start, method_start = struct.unpack_from("<ii", data, b + 36)
    counts = struct.unpack_from("<8H", data, b + 68)
    method_count, prop_count, field_count, event_count, nested_count, vtable_count, ifaces_count, iface_offs_count = counts
    img = "?"
    for nm, (ts, te) in ranges.items():
        if ts <= i < te:
            img = nm
            break
    print(f"\n### [{i}] {ns}.{name}  (image {img})")
    print(f"    fields[{field_start}+{field_count}] methods[{method_start}+{method_count}]")
    for j in range(field_start, field_start + field_count):
        nidx, tidx = struct.unpack_from("<II", data, fld_off + j * FLD)
        print(f"      field {get_str(nidx)}")
    for j in range(method_start, method_start + method_count):
        nidx = struct.unpack_from("<I", data, mtd_off + j * MTD)[0]
        pcount = struct.unpack_from("<H", data, mtd_off + j * MTD + 38)[0]
        print(f"      method {get_str(nidx)}({pcount} params)")


print("=== Axlebolt.Standoff.Anitcheat.AntiCheatManager ===")
dump_type(12236)

# find SystemWatch in Bolt.Api.dll
print("\n=== search SystemWatch / Anticheat namespaces in all images ===")
pat = re.compile(r"(?i)cheat|systemwatch|watch")
for i in range(n_td):
    b = td_off + i * TD
    name = get_str(struct.unpack_from("<I", data, b)[0])
    ns = get_str(struct.unpack_from("<I", data, b + 4)[0])
    full = f"{ns}.{name}"
    if "Anticheat" in full or "Anitcheat" in full or "SystemWatch" in full:
        dump_type(i)