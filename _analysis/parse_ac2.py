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
n_td = td_size // TD


def decode_mtd_for(index):
    """Find MTD size by validating method names for a range."""
    for MTD in (40, 44, 36, 48, 32):
        ok = 0
        bad = 0
        for j in range(index, index + 17):
            nidx = struct.unpack_from("<I", data, mtd_off + j * MTD)[0]
            s = get_str(nidx)
            if s is None:
                bad += 1
            else:
                # method names usually valid C# identifiers
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_`<>.\[\]$]*", s):
                    ok += 1
                else:
                    bad += 1
        print(f"  MTD={MTD}: ok={ok} bad={bad}")


print("validating MTD size on AntiCheatManager methods (start 3836):")
decode_mtd_for(3836)

# Also validate on a big known class: use methods 0..20
print("\nvalidating MTD size on methods 0..20:")
for MTD in (40, 44, 36, 48, 32):
    ok = bad = 0
    for j in range(0, 20):
        nidx = struct.unpack_from("<I", data, mtd_off + j * MTD)[0]
        s = get_str(nidx)
        if s and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_`<>.\[\]$]*", s):
            ok += 1
        else:
            bad += 1
    print(f"  MTD={MTD}: ok={ok} bad={bad}")

# total method count check
print("\nmethods total size check:", mtd_size, "-> /40 =", mtd_size // 40, " /44 =", mtd_size // 44)