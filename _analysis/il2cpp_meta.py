import struct, sys, os

data = open(sys.argv[1], "rb").read()

magic, version = struct.unpack_from("<II", data, 0)
print(f"magic=0x{magic:08x} version={version}")
assert magic == 0xFAB11BAF, "not il2cpp metadata"

fields = [
    "sanity",
    "version",
    "stringLiteralOffset", "stringLiteralSize",
    "stringLiteralDataOffset", "stringLiteralDataSize",
    "stringOffset", "stringSize",
    "eventsOffset", "eventsSize",
    "propertiesOffset", "propertiesSize",
    "methodsOffset", "methodsSize",
    "parameterDefaultValuesOffset", "parameterDefaultValuesSize",
    "fieldDefaultValuesOffset", "fieldDefaultValuesSize",
    "fieldAndParameterDefaultValueDataOffset", "fieldAndParameterDefaultValueDataSize",
    "fieldMarshaledSizesOffset", "fieldMarshaledSizesSize",
    "parametersOffset", "parametersSize",
    "fieldsOffset", "fieldsSize",
    "genericParametersOffset", "genericParametersSize",
    "genericParameterConstraintsOffset", "genericParameterConstraintsSize",
    "genericContainersOffset", "genericContainersSize",
    "nestedTypesOffset", "nestedTypesSize",
    "interfacesOffset", "interfacesSize",
    "vtableMethodsOffset", "vtableMethodsSize",
    "interfaceOffsetsOffset", "interfaceOffsetsSize",
    "typeDefinitionsOffset", "typeDefinitionsSize",
    "imagesOffset", "imagesSize",
    "assembliesOffset", "assembliesSize",
    "metadataUsageListsOffset", "metadataUsageListsSize",
    "metadataUsagePairsOffset", "metadataUsagePairsSize",
    "fieldRefsOffset", "fieldRefsSize",
    "referencedAssembliesOffset", "referencedAssembliesSize",
    "attributesInfoOffset", "attributesInfoSize",
    "attributeTypesOffset", "attributeTypesSize",
    "unresolvedVirtualCallParameterTypesOffset", "unresolvedVirtualCallParameterTypesSize",
    "unresolvedVirtualCallParameterRangesOffset", "unresolvedVirtualCallParameterRangesSize",
    "windowsRuntimeTypeNamesOffset", "windowsRuntimeTypeNamesSize",
    "windowsRuntimeStringsOffset", "windowsRuntimeStringsSize",
    "exportedTypeDefinitionsOffset", "exportedTypeDefinitionsSize",
]

hdr = {}
off = 0
for f in fields:
    hdr[f] = struct.unpack_from("<I", data, off)[0]
    off += 4

so = hdr["stringOffset"]
ssz = hdr["stringSize"]
print(f"string table: offset=0x{so:x} size=0x{ssz:x}")


def get_string(o):
    end = data.find(b"\x00", so + o)
    return data[so + o:end].decode("utf-8", "replace")


# Il2CppImage (v24): nameIndex, assemblyIndex, typeStart, typeCount, exportedTypeStart, exportedTypeCount, customAttributeStart, customAttributeCount, entryPointIndex, token, customAttributePool
img_size = 44
n_img = hdr["imagesSize"] // img_size
io = hdr["imagesOffset"]
print(f"\n== IMAGES ({n_img}) ==")
for i in range(n_img):
    base = io + i * img_size
    name_index, asm_index = struct.unpack_from("<II", data, base)
    print(f"  [{i}] {get_string(name_index)}")

# Il2CppAssemblyName: nameIndex, cultureIndex, hashValueIndex, publicKeyIndex, hash_alg, hash_len, flags, major, minor, build, rev, publicKeyToken[8]
asm_size = 60
n_asm = hdr["assembliesSize"] // asm_size
ao = hdr["assembliesOffset"]
print(f"\n== ASSEMBLIES ({n_asm}) ==")
for i in range(n_asm):
    base = ao + i * asm_size
    name_index = struct.unpack_from("<I", data, base)[0]
    print(f"  [{i}] {get_string(name_index)}")