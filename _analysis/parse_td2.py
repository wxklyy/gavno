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
    end = region.find(b"\x00", o)
    return region[o:end].decode("utf-8", "replace")


WANT_NAME_OFF = {1223211, 1239172, 1181505}
WANT_NS_OFF = {1181400, 1217878}

# Il2CppTypeDefinition v24.1/v24.2 = 88 bytes? try both 88 and 92
for TD in (88, 92, 96):
    n = td_size // TD
    hits = []
    for i in range(n):
        base = td_off + i * TD
        name_index, ns_index = struct.unpack_from("<II", data, base)
        if name_index in WANT_NAME_OFF or ns_index in WANT_NS_OFF:
            hits.append(i)
    if hits:
        print(f"### TD size {TD}: hits at indices {hits}")
        for i in hits:
            base = td_off + i * TD
            name_index, ns_index = struct.unpack_from("<II", data, base)
            print(f"    type[{i}]: name={get_str(name_index)} ns={get_str(ns_index)}")
        break

# Il2CppImage v24 size candidates
for IMG in (44, 48, 52, 40):
    n = img_size // IMG
    ok = 0
    out = []
    for i in range(n):
        base = img_off + i * IMG
        name_index = struct.unpack_from("<I", data, base)[0]
        if name_index < str_size:
            s = get_str(name_index)
            if s.endswith(".dll") or s in ("mscorlib", "Assembly-CSharp", "Assembly-CSharp-firstpass"):
                ok += 1
            out.append(s)
    dlls = [s for s in out if s.endswith(".dll")]
    print(f"IMG={IMG}: n={n} plausible={ok} dll-images={len(dlls)}")
    if len(dlls) > 20:
        print("   sample:", [s for s in out if s.endswith(".dll")][:30])