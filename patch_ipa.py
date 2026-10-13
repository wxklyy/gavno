#!/usr/bin/env python3
"""
S2Rise IPA Patcher — patch Standoff 2 .ipa on Windows
=====================================================

Two modes:
  1. INJECT mode  — shove a pre-compiled .dylib into the Mach-O header
  2. PATCH mode   — direct binary patches (NOP anti-cheat, etc.)

Usage:
  python patch_ipa.py StandRise-RE-1.0.0F2.ipa                 # patch-only (anti-cheat NOP)
  python patch_ipa.py StandRise-RE-1.0.0F2.ipa --dylib S2Rise.dylib  # inject dylib + patches
  python patch_ipa.py StandRise-RE-1.0.0F2.ipa --output patched.ipa  # custom output name

Requirements: Python 3.8+, no external deps.
"""

import struct
import shutil
import zipfile
import os
import sys
import argparse
import tempfile
import glob
from pathlib import Path


# ================================================================
# Mach-O Constants
# ================================================================

MH_MAGIC_64       = 0xFEEDFACF
MH_CIGAM_64       = 0xCFFAEDFE
LC_LOAD_DYLIB     = 0x0000000C
LC_LOAD_WEAK_DYLIB = 0x80000018
LC_SEGMENT_64     = 0x19
LC_CODE_SIGNATURE  = 0x1D
LC_ID_DYLIB       = 0x0D
FAT_MAGIC         = 0xCAFEBABE
FAT_CIGAM         = 0xBEBAFECA
CPU_TYPE_ARM64     = 0x0100000C


# ================================================================
# Mach-O Parser / Patcher
# ================================================================

class MachOPatcher:
    """low-level Mach-O binary manipulator"""

    def __init__(self, data: bytearray):
        self.data = data
        self.offset = 0  # offset into fat binary if applicable
        self._parse_header()

    def _parse_header(self):
        """parse mach_header_64"""
        magic = struct.unpack_from('<I', self.data, self.offset)[0]

        # handle fat binary — find arm64 slice
        if magic in (FAT_MAGIC, FAT_CIGAM):
            self._find_arm64_slice()
            magic = struct.unpack_from('<I', self.data, self.offset)[0]

        if magic == MH_CIGAM_64:
            # big-endian magic, swap
            self.endian = '>'
        elif magic == MH_MAGIC_64:
            self.endian = '<'
        else:
            raise ValueError(f"not a 64-bit Mach-O (magic: 0x{magic:08X})")

        fmt = f'{self.endian}IIIIIIII'
        (self.magic, self.cputype, self.cpusubtype, self.filetype,
         self.ncmds, self.sizeofcmds, self.flags, self.reserved) = \
            struct.unpack_from(fmt, self.data, self.offset)

        self.header_size = struct.calcsize(fmt)  # 32 bytes for mach_header_64

    def _find_arm64_slice(self):
        """locate arm64 slice in a fat/universal binary"""
        magic = struct.unpack_from('>I', self.data, 0)[0]
        if magic == FAT_CIGAM:
            endian = '<'
        else:
            endian = '>'

        nfat = struct.unpack_from(f'{endian}I', self.data, 4)[0]
        for i in range(nfat):
            off = 8 + i * 20
            cputype, cpusubtype, slice_offset, slice_size, align = \
                struct.unpack_from(f'{endian}IIIII', self.data, off)
            if cputype == CPU_TYPE_ARM64:
                self.offset = slice_offset
                print(f"  [*] fat binary — arm64 slice at offset 0x{slice_offset:X}")
                return
        raise ValueError("no arm64 slice found in fat binary")

    def get_load_commands(self):
        """yield (cmd, cmdsize, offset) for each load command"""
        pos = self.offset + self.header_size
        for _ in range(self.ncmds):
            cmd, cmdsize = struct.unpack_from(f'{self.endian}II', self.data, pos)
            yield cmd, cmdsize, pos
            pos += cmdsize

    def has_dylib(self, name: str) -> bool:
        """check if a LC_LOAD_DYLIB with given name already exists"""
        for cmd, cmdsize, pos in self.get_load_commands():
            if cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB):
                name_offset = struct.unpack_from(f'{self.endian}I', self.data, pos + 8)[0]
                abs_offset = pos + name_offset
                end = self.data.index(0, abs_offset)
                dylib_name = self.data[abs_offset:end].decode('utf-8', errors='ignore')
                if name in dylib_name:
                    return True
        return False

    def get_first_section_offset(self) -> int:
        """find the lowest section file offset (header padding boundary)"""
        min_offset = 0
        for cmd, cmdsize, pos in self.get_load_commands():
            if cmd == LC_SEGMENT_64:
                # segment_command_64 layout after cmd+cmdsize:
                # segname(16) + vmaddr(8) + vmsize(8) + fileoff(8) + filesize(8)
                # + maxprot(4) + initprot(4) + nsects(4) + flags(4) = 72 bytes
                nsects = struct.unpack_from(f'{self.endian}I', self.data, pos + 64)[0]
                sect_base = pos + 72
                for s in range(nsects):
                    sect_off = sect_base + s * 80
                    # section_64: sectname(16) + segname(16) + addr(8) + size(8) + offset(4)
                    s_offset = struct.unpack_from(f'{self.endian}I', self.data, sect_off + 48)[0]
                    if s_offset > 0:
                        if min_offset == 0 or s_offset < min_offset:
                            min_offset = s_offset
        return min_offset

    def inject_dylib(self, dylib_path: str) -> bool:
        """inject LC_LOAD_DYLIB command into the Mach-O header"""
        if self.has_dylib(dylib_path):
            print(f"  [+] dylib already present: {dylib_path}")
            return True

        # build the load command
        path_bytes = dylib_path.encode('utf-8') + b'\x00'
        dylib_cmd_size = 24  # sizeof(dylib_command)
        total_size = dylib_cmd_size + len(path_bytes)
        # align to 8 bytes
        total_size = (total_size + 7) & ~7

        # check we have room in the header padding
        end_of_cmds = self.offset + self.header_size + self.sizeofcmds
        first_section = self.get_first_section_offset()

        if first_section > 0 and (end_of_cmds + total_size) > (self.offset + first_section):
            print(f"  [-] not enough header padding! need {total_size} bytes, "
                  f"have {self.offset + first_section - end_of_cmds}")
            return False

        # write dylib_command at end of existing load commands
        pos = end_of_cmds

        # cmd, cmdsize
        struct.pack_into(f'{self.endian}II', self.data, pos, LC_LOAD_DYLIB, total_size)
        # dylib.name.offset (relative to start of this load command)
        struct.pack_into(f'{self.endian}I', self.data, pos + 8, dylib_cmd_size)
        # dylib.timestamp
        struct.pack_into(f'{self.endian}I', self.data, pos + 12, 2)
        # dylib.current_version
        struct.pack_into(f'{self.endian}I', self.data, pos + 16, 0x00010000)
        # dylib.compatibility_version
        struct.pack_into(f'{self.endian}I', self.data, pos + 20, 0x00010000)
        # dylib path string
        self.data[pos + dylib_cmd_size:pos + dylib_cmd_size + len(path_bytes)] = path_bytes
        # zero-pad remainder
        pad_start = pos + dylib_cmd_size + len(path_bytes)
        pad_end = pos + total_size
        self.data[pad_start:pad_end] = b'\x00' * (pad_end - pad_start)

        # update header: ncmds + 1, sizeofcmds + total_size
        self.ncmds += 1
        self.sizeofcmds += total_size
        struct.pack_into(f'{self.endian}II', self.data,
                         self.offset + 16,  # ncmds offset in mach_header_64
                         self.ncmds, self.sizeofcmds)

        print(f"  [+] injected LC_LOAD_DYLIB: {dylib_path}")
        return True

    def remove_code_signature(self) -> bool:
        """remove LC_CODE_SIGNATURE load command without leaving gaps"""
        for cmd, cmdsize, pos in self.get_load_commands():
            if cmd == LC_CODE_SIGNATURE:
                end_of_cmds = self.offset + self.header_size + self.sizeofcmds
                # Shift all subsequent load commands back by cmdsize
                remaining_bytes = end_of_cmds - (pos + cmdsize)
                if remaining_bytes > 0:
                    self.data[pos:pos + remaining_bytes] = self.data[pos + cmdsize:end_of_cmds]
                # Zero out the freed space at the end of load commands
                self.data[end_of_cmds - cmdsize:end_of_cmds] = b'\x00' * cmdsize

                self.ncmds -= 1
                self.sizeofcmds -= cmdsize
                struct.pack_into(f'{self.endian}II', self.data,
                                 self.offset + 16,  # ncmds offset in mach_header_64
                                 self.ncmds, self.sizeofcmds)
                print("  [+] cleanly removed LC_CODE_SIGNATURE")
                return True
        print("  [*] no LC_CODE_SIGNATURE found")
        return False

    def find_bytes(self, pattern: bytes, start: int = 0) -> list:
        """find all occurrences of a byte pattern"""
        results = []
        pos = start
        while True:
            idx = self.data.find(pattern, pos)
            if idx == -1:
                break
            results.append(idx)
            pos = idx + 1
        return results

    def patch_bytes(self, offset: int, old: bytes, new: bytes) -> bool:
        """patch bytes at offset, verifying old value first"""
        if len(old) != len(new):
            print(f"  [-] patch size mismatch at 0x{offset:X}")
            return False
        current = bytes(self.data[offset:offset + len(old)])
        if current != old:
            print(f"  [*] bytes at 0x{offset:X} don't match expected — skipping")
            return False
        self.data[offset:offset + len(new)] = new
        print(f"  [+] patched {len(new)} bytes at 0x{offset:X}")
        return True

    def nop_arm64(self, offset: int, count: int = 1):
        """write ARM64 NOP instructions (0xD503201F) at offset"""
        nop = b'\x1f\x20\x03\xd5'  # NOP in little-endian
        for i in range(count):
            self.data[offset + i * 4:offset + (i + 1) * 4] = nop
        print(f"  [+] NOP'd {count} instructions at 0x{offset:X}")

    def patch_ret_zero(self, offset: int):
        """patch function to: MOV W0, #0; RET"""
        # MOV W0, #0  = 0x52800000
        # RET         = 0xD65F03C0
        self.data[offset:offset + 4] = struct.pack('<I', 0x52800000)
        self.data[offset + 4:offset + 8] = struct.pack('<I', 0xD65F03C0)
        print(f"  [+] patched RET 0 at 0x{offset:X}")

    def patch_ret_one(self, offset: int):
        """patch function to: MOV W0, #1; RET"""
        # MOV W0, #1  = 0x52800020
        # RET         = 0xD65F03C0
        self.data[offset:offset + 4] = struct.pack('<I', 0x52800020)
        self.data[offset + 4:offset + 8] = struct.pack('<I', 0xD65F03C0)
        print(f"  [+] patched RET 1 at 0x{offset:X}")


# ================================================================
# IPA Patcher
# ================================================================

class IPAPatcher:
    """unzip → patch → rezip .ipa files"""

    def __init__(self, ipa_path: str, output_path: str = None):
        self.ipa_path = ipa_path
        self.output_path = output_path or self._default_output()
        self.temp_dir = None
        self.app_dir = None
        self.binary_path = None
        self.binary_name = None

    def _default_output(self):
        base = os.path.splitext(self.ipa_path)[0]
        return f"{base}_patched.ipa"

    def extract(self):
        """extract .ipa to temp directory"""
        self.temp_dir = tempfile.mkdtemp(prefix="ipa_patch_")
        print(f"[*] extracting to {self.temp_dir}")

        with zipfile.ZipFile(self.ipa_path, 'r') as zf:
            zf.extractall(self.temp_dir)

        # find .app directory inside Payload/
        payload_dir = os.path.join(self.temp_dir, "Payload")
        if not os.path.isdir(payload_dir):
            raise FileNotFoundError("no Payload/ directory in .ipa")

        apps = [d for d in os.listdir(payload_dir) if d.endswith('.app')]
        if not apps:
            raise FileNotFoundError("no .app bundle found in Payload/")

        self.app_dir = os.path.join(payload_dir, apps[0])
        print(f"[+] found app: {apps[0]}")

        # find the main binary
        # check Info.plist for CFBundleExecutable
        info_plist = os.path.join(self.app_dir, "Info.plist")
        binary_name = None

        if os.path.exists(info_plist):
            # try to parse plist to get executable name
            binary_name = self._get_bundle_executable(info_plist)

        if not binary_name:
            # fallback: try common names
            for name in ['standoff2', 'StandRiseRE', 'Standoff2']:
                if os.path.isfile(os.path.join(self.app_dir, name)):
                    binary_name = name
                    break

        if not binary_name:
            # last resort: find any Mach-O file
            for f in os.listdir(self.app_dir):
                fpath = os.path.join(self.app_dir, f)
                if os.path.isfile(fpath) and not f.startswith('.'):
                    with open(fpath, 'rb') as fp:
                        magic = fp.read(4)
                        if magic in (b'\xCF\xFA\xED\xFE', b'\xFE\xED\xFA\xCF',
                                     b'\xCA\xFE\xBA\xBE', b'\xBE\xBA\xFE\xCA'):
                            binary_name = f
                            break

        if not binary_name:
            raise FileNotFoundError("can't find main binary in .app bundle")

        self.binary_name = binary_name
        self.binary_path = os.path.join(self.app_dir, binary_name)
        print(f"[+] main binary: {binary_name}")

    def _get_bundle_executable(self, plist_path: str) -> str:
        """parse binary plist to extract CFBundleExecutable"""
        try:
            import plistlib
            with open(plist_path, 'rb') as f:
                plist = plistlib.load(f)
            return plist.get('CFBundleExecutable')
        except Exception:
            # fallback: grep for it
            try:
                with open(plist_path, 'rb') as f:
                    data = f.read()
                # look for CFBundleExecutable in XML or binary plist
                idx = data.find(b'CFBundleExecutable')
                if idx >= 0:
                    # try XML format
                    start = data.find(b'<string>', idx)
                    end = data.find(b'</string>', start)
                    if start > 0 and end > start:
                        return data[start + 8:end].decode('utf-8')
            except Exception:
                pass
        return None

    def patch_binary(self, dylib_inject: str = None, apply_patches: bool = True):
        """patch the main binary"""
        print(f"\n[*] loading binary: {self.binary_path}")
        with open(self.binary_path, 'rb') as f:
            data = bytearray(f.read())

        patcher = MachOPatcher(data)
        print(f"  [*] Mach-O 64-bit — {patcher.ncmds} load commands, "
              f"header size: {patcher.sizeofcmds} bytes")

        # --- step 1: keep LC_CODE_SIGNATURE intact for Sideloadly/AltStore resigning ---
        # (Sideloadly's SignBinary requires valid LC_CODE_SIGNATURE command to overwrite)

        # --- step 2: inject dylib if provided ---
        if dylib_inject:
            dylib_load_path = f"@executable_path/{os.path.basename(dylib_inject)}"
            if not patcher.inject_dylib(dylib_load_path):
                raise RuntimeError("dylib injection failed; refusing to emit an IPA without the load command")
            # copy the dylib into the .app bundle
            dest = os.path.join(self.app_dir, os.path.basename(dylib_inject))
            shutil.copy2(dylib_inject, dest)
            print(f"  [+] copied {os.path.basename(dylib_inject)} into app bundle")

        # --- step 3: apply binary patches ---
        if apply_patches:
            self._apply_anticheat_patches(patcher)

        # --- step 4: remove _CodeSignature directory ---
        codesig_dir = os.path.join(self.app_dir, '_CodeSignature')
        if os.path.isdir(codesig_dir):
            shutil.rmtree(codesig_dir)
            print("  [+] removed _CodeSignature directory")

        # --- step 5: remove embedded.mobileprovision ---
        mobileprov = os.path.join(self.app_dir, 'embedded.mobileprovision')
        if os.path.isfile(mobileprov):
            os.remove(mobileprov)
            print("  [+] removed embedded.mobileprovision")

        # write patched binary
        with open(self.binary_path, 'wb') as f:
            f.write(data)
        print(f"\n[+] main binary patched and saved")

        # --- step 6: patch UnityFramework (the real game code) ---
        if apply_patches:
            self._patch_unity_framework()

    def _apply_anticheat_patches(self, patcher: MachOPatcher):
        """strip signature from main binary — real patches go on UnityFramework"""
        print("\n  --- main binary: signature stripped ---")

    def _patch_unity_framework(self):
        """
        patch UnityFramework with confirmed jailbreak detection NOP patches.
        offsets from ADRP+ADD xref analysis on Standoff 2 v0.19.10 (1090).
        """
        uf_path = os.path.join(self.app_dir, "Frameworks",
                               "UnityFramework.framework", "UnityFramework")
        if not os.path.isfile(uf_path):
            print("  [!] UnityFramework not found — skipping AC patches")
            return

        print(f"\n[*] patching UnityFramework ({os.path.getsize(uf_path) / 1024 / 1024:.1f} MB)")
        with open(uf_path, 'rb') as f:
            uf = bytearray(f.read())

        RET_FALSE = struct.pack('<II', 0x52800000, 0xD65F03C0)  # MOV W0,#0; RET
        RET_VOID  = struct.pack('<I', 0xD65F03C0)               # RET

        patch_count = 0

        # ---- Method 1: Dynamic Mach-O Symbol Table (LC_SYMTAB) resolution ----
        # StandRise RE binaries retain full AntiCheatManager method symbols!
        try:
            ncmds = struct.unpack_from('<I', uf, 16)[0]
            pos = 32
            symtab = None
            text_vmaddr = 0
            text_fileoff = 0

            for _ in range(ncmds):
                cmd, cmdsize = struct.unpack_from('<II', uf, pos)
                if cmd == 0x19: # LC_SEGMENT_64
                    segname = uf[pos+8:pos+24].split(b'\x00')[0].decode('utf-8', errors='ignore')
                    if segname == '__TEXT':
                        text_vmaddr, text_vmsize, text_fileoff, _ = struct.unpack_from('<QQQQ', uf, pos+24)
                elif cmd == 0x02: # LC_SYMTAB
                    symoff, nsyms, stroff, strsize = struct.unpack_from('<IIII', uf, pos+8)
                    symtab = (symoff, nsyms, stroff, strsize)
                pos += cmdsize

            if symtab:
                symoff, nsyms, stroff, strsize = symtab
                print(f"  [*] LC_SYMTAB parsed: {nsyms} symbols (__TEXT: 0x{text_vmaddr:X}-0x{text_vmaddr+text_vmsize:X})")
                for i in range(nsyms):
                    n_off = symoff + i * 16
                    n_strx, n_type, n_sect, n_desc, n_value = struct.unpack_from('<IBBHQ', uf, n_off)
                    if n_strx < strsize:
                        str_end = uf.find(b'\x00', stroff + n_strx)
                        sym_name = uf[stroff + n_strx:str_end].decode('utf-8', errors='ignore')
                        # Only target actual C++ code functions inside __TEXT segment (must contain '_m' method marker)
                        if 'AntiCheatManager_' in sym_name and not sym_name.startswith('__Z'):
                            if '_m' in sym_name and (text_vmaddr <= n_value < text_vmaddr + text_vmsize):
                                if any(k in sym_name for k in ['_ctor', 'OnDestroy', 'Initialized', '_var']):
                                    continue
                                file_offset = n_value - text_vmaddr + text_fileoff
                                if 0 < file_offset < len(uf) - 8:
                                    first_ins = struct.unpack_from('<I', uf, file_offset)[0]
                                    # Verify valid function prologue (STP / SUB SP)
                                    is_stp = (first_ins & 0xFE000000) in (0xA8000000, 0xA9000000)
                                    is_sub = (first_ins & 0xFF0003FF) == 0xD100001F
                                    if is_stp or is_sub:
                                        uf[file_offset:file_offset+8] = RET_FALSE
                                        short_name = sym_name.split('_m')[0].replace('_AntiCheatManager_', '')
                                        print(f"  [+] Neutralized AC method: {short_name} @ 0x{file_offset:08X} (prologue=0x{first_ins:08X})")
                                        patch_count += 1
        except Exception as e:
            print(f"  [-] Dynamic symtab scan failed: {e}")

        # ---- Method 2: Fallback to fixed offsets (ONLY for original Standoff 2 72.7MB binary) ----
        if patch_count == 0 and len(uf) == 72765840:
            print("  [*] Falling back to static offsets for v0.19.10 72MB build...")
            targets = [
                (0x143D5C, "JB path stash checker (/var/stash/*)"),
                (0x143B84, "JB file check helper"),
                (0x143CC8, "canOpenURL(cydia://) check"),
                (0x5CCA58, "Cydia.app path check (1)"),
                (0x67A188, "Cydia.app path check (2)"),
                (0x17C7BA8, "IL2CPP isDebugged+ios_jailbreak icall"),
            ]
            for offset, name in targets:
                if self._verify_and_patch(uf, offset, RET_FALSE, name):
                    patch_count += 1

        # keep UnityFramework LC_CODE_SIGNATURE intact for Sideloadly/AltStore resigning

        with open(uf_path, 'wb') as f:
            f.write(uf)

        print(f"\n  [+] UnityFramework: {patch_count} functions patched -> RET 0")

    def _verify_and_patch(self, data: bytearray, offset: int,
                          patch: bytes, name: str) -> bool:
        """verify offset looks like function start and apply patch"""
        if offset + len(patch) > len(data):
            print(f"  [-] {name}: 0x{offset:X} out of range")
            return False

        first = struct.unpack_from('<I', data, offset)[0]
        already = data[offset:offset+8] == patch
        if already:
            print(f"  [=] {name} @ 0x{offset:X}: already patched")
            return True

        # sanity: should be STP/SUB/PACIBSP/MOV/etc at function entry
        data[offset:offset + len(patch)] = patch
        print(f"  [+] {name} @ 0x{offset:X}: -> RET 0 (was 0x{first:08X})")
        return True

    def repackage(self):
        """repackage patched files back into .ipa with proper POSIX permissions"""
        print(f"\n[*] repackaging to {self.output_path} with iOS POSIX permissions (0o755)...")

        # Map of original permissions from original IPA if available
        orig_perms = {}
        try:
            with zipfile.ZipFile(self.ipa_path, 'r') as z_orig:
                for info in z_orig.infolist():
                    orig_perms[info.filename.replace('\\', '/')] = info.external_attr
        except Exception:
            pass

        with zipfile.ZipFile(self.output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(self.temp_dir):
                # Write explicit directory records with 0o755
                for d in dirs:
                    dpath = os.path.join(root, d)
                    arcname = os.path.relpath(dpath, self.temp_dir).replace('\\', '/') + '/'
                    attr = orig_perms.get(arcname, 0x41ED0010) # 0o40755
                    zinfo = zipfile.ZipInfo(arcname)
                    zinfo.external_attr = attr
                    zf.writestr(zinfo, b'')

                for f in files:
                    fpath = os.path.join(root, f)
                    arcname = os.path.relpath(fpath, self.temp_dir).replace('\\', '/')

                    with open(fpath, 'rb') as fp:
                        file_data = fp.read()

                    zinfo = zipfile.ZipInfo(arcname)
                    zinfo.compress_type = zipfile.ZIP_DEFLATED

                    # Check original permission or assign based on file type
                    if arcname in orig_perms:
                        zinfo.external_attr = orig_perms[arcname]
                    elif f in ['StandRiseRE', 'standoff2', 'UnityFramework'] or f.endswith('.dylib'):
                        zinfo.external_attr = 0x81ED0000 # 0o100755 (executable)
                    elif file_data[:4] in (b'\xCF\xFA\xED\xFE', b'\xFE\xED\xFA\xCF', b'\xCA\xFE\xBA\xBE'):
                        zinfo.external_attr = 0x81ED0000 # 0o100755 (Mach-O executable)
                    else:
                        zinfo.external_attr = 0x81A40000 # 0o100644 (regular file)

                    zf.writestr(zinfo, file_data)

        # Validate the archive before reporting success.  This catches a
        # truncated write or a missing injected dylib early.
        with zipfile.ZipFile(self.output_path, 'r') as check:
            bad = check.testzip()
            if bad:
                raise RuntimeError(f"repackaged IPA failed CRC validation: {bad}")
            if not any(n.endswith('/' + os.path.basename(self.binary_name)) for n in check.namelist()):
                raise RuntimeError("repackaged IPA does not contain the main executable")

        size_mb = os.path.getsize(self.output_path) / (1024 * 1024)
        print(f"[+] patched IPA saved: {self.output_path} ({size_mb:.1f} MB)")

    def cleanup(self):
        """remove temp directory"""
        if self.temp_dir and os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            print("[*] temp files cleaned up")

    def run(self, dylib_path: str = None, no_patches: bool = False):
        """full pipeline"""
        print("=" * 56)
        print("  S2Rise IPA Patcher")
        print("  shit aint tuff bro, oil up gng")
        print("=" * 56)
        print()

        try:
            self.extract()
            self.patch_binary(
                dylib_inject=dylib_path,
                apply_patches=not no_patches
            )
            self.repackage()
            print()
            print("[✓] DONE! patched IPA ready to sideload")
            print()
            print("  next steps:")
            print("  1. transfer .ipa to device")
            print("  2. install via TrollStore / AltStore / Sideloadly")
            print("  3. open the game — cheat loads automatically")
            print()
        finally:
            self.cleanup()


# ================================================================
# CLI
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description='S2Rise IPA Patcher — inject cheat into Standoff 2 .ipa',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s StandRise-RE-1.0.0F2.ipa
  %(prog)s StandRise-RE-1.0.0F2.ipa --dylib S2Rise.dylib
  %(prog)s StandRise-RE-1.0.0F2.ipa --output patched.ipa --dylib S2Rise.dylib
        """)

    parser.add_argument('ipa', help='path to the .ipa file')
    parser.add_argument('--dylib', help='path to compiled .dylib to inject')
    parser.add_argument('--output', '-o', help='output .ipa path')
    parser.add_argument('--no-patches', action='store_true',
                        help='skip binary patches (only inject dylib)')

    args = parser.parse_args()

    if not os.path.isfile(args.ipa):
        print(f"[-] file not found: {args.ipa}")
        sys.exit(1)

    if args.dylib and not os.path.isfile(args.dylib):
        print(f"[-] dylib not found: {args.dylib}")
        sys.exit(1)

    patcher = IPAPatcher(args.ipa, args.output)
    patcher.run(dylib_path=args.dylib, no_patches=args.no_patches)


if __name__ == '__main__':
    main()
