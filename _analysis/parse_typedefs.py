import struct, sys, re

data = open(sys.argv[1], "rb").read()
hdr = struct.unpack_from("<%dI" % (2 + 29 * 2), data, 0)
pairs = [(hdr[i], hdr[i + 1]) for i in range(2, 2 + 29 * 2, 2)]

str_off, str_size = pairs[2]


def get_str(o):
    end = data.find(b"\x00", str_off + o)
    return data[str_off + o:end].decode("utf-8", "replace")


# v24: fieldAndParameterDefaultValueData idx 7, typeDefinitions idx 23 (0-based in pairs)
# pairs list order matches the field list in il2cpp_meta.py:
# 0 slit, 1 slitdata, 2 string, 3 events, 4 properties, 5 methods, 6 paramDefault,
# 7 fieldDefault, 8 fieldAndParameterDefaultValueData, 9 fieldMarshaledSizes,
# 10 parameters, 11 fields, 12 genericParameters, 13 genericParameterConstraints,
# 14 genericContainers, 15 nestedTypes, 16 interfaces, 17 vtableMethods,
# 18 interfaceOffsets, 19 typeDefinitions, 20 images, 21 assemblies, ...
td_off, td_size = pairs[19]
img_off, img_size = pairs[20]

# Il2CppImage v24 (44 bytes): nameIndex, assemblyIndex, typeStart, typeCount,
# exportedTypeStart, exportedTypeCount, customAttributeStart, customAttributeCount,
# entryPointIndex, token, customAttributePool
IMG = 44
n_img = img_size // IMG
images = []
for i in range(n_img):
    base = img_off + i * IMG
    name_index, asm_index, type_start, type_count = struct.unpack_from("<IIII", data, base)
    images.append((get_str(name_index), type_start, type_count))

print(f"images: {n_img}")
for nm, ts, tc in images:
    if nm and (nm.endswith(".dll") or "Assembly" in nm or nm == "mscorlib"):
        print(f"  {nm}: typeStart={ts} typeCount={tc}")

# Il2CppTypeDefinition v24 layout (88 bytes):
# nameIndex, namespaceIndex, byvalTypeIndex, byrefTypeIndex,
# declaringTypeIndex, parentIndex, elementTypeIndex,
# rgctxStartIndex, rgctxCount,
# genericContainerIndex,
# flags,
# fieldStart, methodStart, eventStart, propertyStart, nestedTypesStart, interfacesStart, vtableStart, interfaceOffsetsStart,
# method_count, property_count, field_count, event_count, nested_type_count, vtable_count, interfaces_count, interface_offsets_count,
# bitfield, token, customAttributeIndex
TD = 88
n_td = td_size // TD
print(f"\ntypeDefinitions: {n_td}")

pat = re.compile(r"(?i)anticheat|anti.?cheat|antihack|watch|guard|shield|detect|protect")

print("\n== TYPES matching anticheat-ish names ==")
found = []
for i in range(n_td):
    base = td_off + i * TD
    name_index, ns_index = struct.unpack_from("<II", data, base)
    name = get_str(name_index)
    ns = get_str(ns_index)
    full = f"{ns}.{name}" if ns else name
    if pat.search(full):
        # find image
        img = ""
        for nm, ts, tc in images:
            if ts <= i < ts + tc:
                img = nm
                break
        found.append((i, full, img))

for idx, full, img in sorted(found, key=lambda x: x[1]):
    print(f"  [{idx}] {full}   (image: {img})")

print("\ntotal matches:", len(found))