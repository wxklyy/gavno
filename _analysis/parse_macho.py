import struct, sys

MACHO64_MAGIC = 0xFEEDFACF
LC_SEGMENT_64 = 0x19
LC_ENCRYPTION_INFO_64 = 0x2C
LC_LOAD_DYLIB = 0xC
LC_LOAD_DYLINKER = 0xE
LC_RPATH = 0x8000001C
LC_MAIN = 0x80000028
LC_CODE_SIGNATURE = 0x1D
LC_BUILD_VERSION = 0x32
LC_DYLD_CHAINED_FIXUPS = 0x80000034
LC_DYLD_EXPORTS_TRIE = 0x80000033


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def u64(b, o):
    return struct.unpack_from("<Q", b, o)[0]


def cstr(b, o):
    end = b.find(b"\x00", o)
    return b[o:end].decode("utf-8", "replace")


def parse(path):
    data = open(path, "rb").read()
    print(f"== {path} ==")
    print("size:", len(data))
    magic = u32(data, 0)
    if magic == 0xCAFEBABE or magic == 0xBEBAFECA:
        print("FAT binary")
        nfat = struct.unpack_from(">I", data, 4)[0]
        for i in range(nfat):
            off = 8 + i * 20
            cputype, cpusub, foff, fsize, align = struct.unpack_from(">IIIII", data, off)
            print(f"  arch[{i}] cputype=0x{cputype:x} off={foff} size={fsize}")
        return
    if magic != MACHO64_MAGIC:
        print(f"unknown magic 0x{magic:x}")
        return
    cputype = u32(data, 4)
    filetype = u32(data, 12)
    ncmds = u32(data, 16)
    flags = u32(data, 24)
    print(f"cputype=0x{cputype:x} filetype={filetype} ncmds={ncmds} flags=0x{flags:x}")
    print("  PIE" if flags & 0x200000 else "  (no PIE)")
    off = 32
    for i in range(ncmds):
        cmd = u32(data, off)
        cmdsize = u32(data, off + 4)
        if cmd == LC_SEGMENT_64:
            name = data[off + 8:off + 24].rstrip(b"\x00").decode()
            vmsize = u64(data, off + 32)
            fileoff = u64(data, off + 40)
            filesize = u64(data, off + 48)
            maxprot = u32(data, off + 56)
            initprot = u32(data, off + 60)
            nsects = u32(data, off + 64)
            print(f"  SEG {name:<16} vm=0x{vmsize:x} fileoff={fileoff} filesize={filesize} maxprot={maxprot} initprot={initprot} nsects={nsects}")
            so = off + 72
            for s in range(nsects):
                sname = data[so:so + 16].rstrip(b"\x00").decode()
                segname = data[so + 16:so + 32].rstrip(b"\x00").decode()
                ssize = u64(data, so + 40)
                soff = u32(data, so + 48)
                print(f"      SECT {segname},{sname} size=0x{ssize:x} fileoff=0x{soff:x}")
                so += 80
        elif cmd == LC_ENCRYPTION_INFO_64:
            cryptoff = u32(data, off + 8)
            cryptsize = u32(data, off + 12)
            cryptid = u32(data, off + 16)
            print(f"  ENCRYPTION cryptoff={cryptoff} cryptsize={cryptsize} cryptid={cryptid} {'[ENCRYPTED - FairPlay DRM]' if cryptid else '[decrypted]'}")
        elif cmd in (LC_LOAD_DYLIB, 0x18, 0x1F):
            nameo = u32(data, off + 8)
            print(f"  DYLIB {cstr(data, off + nameo)}")
        elif cmd == LC_LOAD_DYLINKER:
            nameo = u32(data, off + 8)
            print(f"  DYLINKER {cstr(data, off + nameo)}")
        elif cmd == LC_RPATH:
            nameo = u32(data, off + 8)
            print(f"  RPATH {cstr(data, off + nameo)}")
        elif cmd == LC_MAIN:
            entry = u64(data, off + 8)
            print(f"  MAIN entryoff=0x{entry:x}")
        elif cmd == LC_CODE_SIGNATURE:
            do = u32(data, off + 8)
            ds = u32(data, off + 12)
            print(f"  CODE_SIGNATURE off={do} size={ds}")
        elif cmd == LC_BUILD_VERSION:
            platform = u32(data, off + 8)
            minos = u32(data, off + 12)
            sdk = u32(data, off + 16)
            print(f"  BUILD_VERSION platform={platform} minos={minos >> 16}.{(minos >> 8) & 0xff}.{minos & 0xff} sdk={sdk >> 16}.{(sdk >> 8) & 0xff}.{sdk & 0xff}")
        elif cmd == LC_DYLD_CHAINED_FIXUPS:
            print("  CHAINED_FIXUPS (dyld chained fixups present)")
        off += cmdsize


for p in sys.argv[1:]:
    parse(p)
    print()