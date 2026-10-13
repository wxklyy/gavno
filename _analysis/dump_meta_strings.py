import struct, sys, re

data = open(sys.argv[1], "rb").read()

# global-metadata.dat header: magic, version, then offset/size pairs.
hdr_vals = struct.unpack_from("<%dI" % (len(data[:8 + 29 * 8]) // 4), data, 0)

# indexes from header (each is 2 ints: offset, size)
# 0: stringLiteral, 1: stringLiteralData, 2: string, ...
pairs = []
for i in range(2, 2 + 29 * 2, 2):
    pairs.append((hdr_vals[i], hdr_vals[i + 1]))

slit_off, slit_size = pairs[0]
slitdata_off, slitdata_size = pairs[1]
str_off, str_size = pairs[2]
print(f"stringLiteral: off=0x{slit_off:x} size=0x{slit_size:x}")
print(f"stringLiteralData: off=0x{slitdata_off:x} size=0x{slitdata_size:x}")
print(f"string: off=0x{str_off:x} size=0x{str_size:x}")

# 1) string table = NUL-separated utf8 strings
out = open(sys.argv[2], "w", encoding="utf-8")
start = 0
count = 0
region = data[str_off:str_off + str_size]
while True:
    nul = region.find(b"\x00", start)
    if nul == -1:
        break
    s = region[start:nul].decode("utf-8", "replace")
    out.write(s + "\n")
    count += 1
    start = nul + 1
out.close()
print("string table entries:", count, "->", sys.argv[2])

# 2) string literals: array of (length:int32, dataIndex:int32), data in stringLiteralData
out2 = open(sys.argv[3], "w", encoding="utf-8")
n = slit_size // 8
for i in range(n):
    length, didx = struct.unpack_from("<II", data, slit_off + i * 8)
    if length > 100000:
        continue
    s = data[slitdata_off + didx: slitdata_off + didx + length].decode("utf-8", "replace")
    out2.write(s.replace("\n", "\\n") + "\n")
out2.close()
print("string literals:", n, "->", sys.argv[3])