import struct, sys, re, bisect

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

# name offsets we care about (find all occurrences)
names_of_interest = ["GameAntiCheatManager", "ColliderAnitСheat2", "Observer", "AnitcheatTesting"]
off_by_name = {}
for nm in names_of_interest:
    enc = nm.encode("utf-8")
    cur = 0
    offs = []
    while True:
        p = region.find(b"\x00" + enc + b"\x00", max(0, cur - 1))
        if p == -1:
            break
        offs.append(p + 1)
        cur = p + 1 + len(enc) + 1
    off_by_name[nm] = set(offs)

print("name offsets:", {k: sorted(v) for k, v in off_by_name.items()})

# scan type definitions: nameIndex at +0
for i in range(n_td):
    nidx = struct.unpack_from("<I", data, td_off + i * TD)[0]
    for nm, offs in off_by_name.items():
        if nidx in offs:
            ns = get_str(struct.unpack_from("<I", data, td_off + i * TD + 4)[0])
            print(f"\n=== type[{i}] {ns}.{nm} <{image_of(i)}> ===")
            field_start, method_start = struct.unpack_from("<ii", data, td_off + i * TD + 36)
            print(f"    field_start={field_start} method_start={method_start}")
            # methods: print method_count from +68 halfword
            mc = struct.unpack_from("<H", data, td_off + i * TD + 68)[0]
            fc = struct.unpack_from("<H", data, td_off + i * TD + 72)[0]
            print(f"    method_count={mc} field_count={fc}")
            if 0 <= method_start and 0 < mc < 200:
                for j in range(method_start, method_start + mc):
                    mn = get_str(struct.unpack_from("<I", data, mtd_off + j * MTD)[0])
                    print(f"      method {mn}")
            if 0 <= field_start and 0 < fc < 100:
                for j in range(field_start, field_start + fc):
                    fn = get_str(struct.unpack_from("<I", data, fld_off + j * FLD)[0])
                    print(f"      field {fn}")