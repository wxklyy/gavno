import struct, sys, re

data = open(sys.argv[1], "rb").read()
hdr = struct.unpack_from("<%dI" % (2 + 29 * 2), data, 0)
pairs = [(hdr[i], hdr[i + 1]) for i in range(2, 2 + 29 * 2, 2)]

str_off, str_size = pairs[2]
mtd_off, mtd_size = pairs[5]
fld_off, fld_size = pairs[11]
td_off, td_size = pairs[19]

region = data[str_off:str_off + str_size]


def get_str(o):
    if o < 0 or o >= str_size:
        return None
    end = region.find(b"\x00", o)
    return region[o:end].decode("utf-8", "replace")


TD = 88
MTD = 32
FLD = 12
n_td = td_size // TD


def dump_type(i):
    b = td_off + i * TD
    name = get_str(struct.unpack_from("<I", data, b)[0])
    ns = get_str(struct.unpack_from("<I", data, b + 4)[0])
    field_start, method_start = struct.unpack_from("<ii", data, b + 36)
    method_count, prop_count, field_count = struct.unpack_from("<HHH", data, b + 68)
    print(f"\n### [{i}] {ns}.{name}")
    print(f"    methods[{method_start}+{method_count}] fields[{field_start}+{field_count}]")
    if 0 <= field_start and field_count < 100:
        for j in range(field_start, field_start + field_count):
            nidx, tidx = struct.unpack_from("<II", data, fld_off + j * FLD)
            print(f"      field {get_str(nidx)}")
    if 0 <= method_start and method_count < 100:
        for j in range(method_start, method_start + method_count):
            nidx = struct.unpack_from("<I", data, mtd_off + j * MTD)[0]
            print(f"      method {get_str(nidx)}")


print("=== AntiCheatManager with MTD=32 ===")
dump_type(12236)

# sanity: dump a known type - find 'GameAntiCheatManager' by name
for i in range(n_td):
    b = td_off + i * TD
    name = get_str(struct.unpack_from("<I", data, b)[0])
    if name == "GameAntiCheatManager":
        dump_type(i)

# all types in namespaces containing nitcheat/Anticheat
print("\n=== all types in anticheat namespaces ===")
seen = set()
for i in range(n_td):
    b = td_off + i * TD
    name = get_str(struct.unpack_from("<I", data, b)[0]) or ""
    ns = get_str(struct.unpack_from("<I", data, b + 4)[0]) or ""
    if re.search(r"(?i)ant[ic]+heat", ns) or re.search(r"(?i)ant[ic]+heat", name) or "SystemWatch" in ns or "SystemWatch" in name:
        if i not in seen:
            seen.add(i)
            dump_type(i)