import struct, sys

data = open(sys.argv[1], "rb").read()
hdr = struct.unpack_from("<%dI" % (2 + 29 * 2), data, 0)
pairs = [(hdr[i], hdr[i + 1]) for i in range(2, 2 + 29 * 2, 2)]

# print all nonzero offset/size pairs with names
names = [
    "stringLiteral", "stringLiteralData", "string", "events", "properties",
    "methods", "parameterDefaultValues", "fieldDefaultValues",
    "fieldAndParameterDefaultValueData", "fieldMarshaledSizes", "parameters",
    "fields", "genericParameters", "genericParameterConstraints",
    "genericContainers", "nestedTypes", "interfaces", "vtableMethods",
    "interfaceOffsets", "typeDefinitions", "images", "assemblies",
    "metadataUsageLists", "metadataUsagePairs", "fieldRefs",
    "referencedAssemblies", "attributesInfo", "attributeTypes",
    "unresolvedVirtualCallParameterTypes", "unresolvedVirtualCallParameterRanges",
]
print("version:", hdr[1])
for nm, (o, s) in zip(names, pairs):
    print(f"  {nm:<45} off=0x{o:>9x} size=0x{s:>9x} ({s})")

str_off, str_size = pairs[2]
region = data[str_off:str_off + str_size]

# build map offset->string
def get_str(o):
    if o >= str_size:
        return f"<bad:{o}>"
    end = region.find(b"\x00", o)
    return region[o:end].decode("utf-8", "replace")

# find all offsets whose string contains 'nticheat' or 'ntihack'
import re
pat = re.compile(rb"[\x01-\x7f]*[nN][tT][iI][cC][hH][eE][aA][tT][\x01-\x7f]*")
print("\n== string-table entries containing '[nN]ticheat' ==")
for m in pat.finditer(region):
    # walk back to string start
    start = region.rfind(b"\x00", 0, m.start()) + 1
    end = region.find(b"\x00", m.start())
    s = region[start:end].decode("utf-8", "replace")
    print(f"  off=0x{start:x} ({start})  {s!r}")