#!/usr/bin/env python3
"""
find_jb_v3.py — scan __text and il2cpp sections for xrefs to JB strings
also check __cfstring table for NSString wrappers
"""
import struct, os, sys

uf_path = r'_analysis\extracted\Frameworks__UnityFramework.framework__UnityFramework'
with open(uf_path, 'rb') as f:
    data = f.read()

size = len(data)
print(f'[*] {size/1024/1024:.1f} MB')

# known code ranges (from section dump)
code_ranges = [
    # (file_offset, size, vma, name)
    (0x00004D70, 0x017C3020, 0x00004D70, '__text'),
    (0x017C7D90, 0x012F8D44, 0x017C7D90, 'il2cpp'),
]

# known JB string file offsets (= VMAs since __TEXT base is 0)
targets = {
    0x351EC1D: 'ios_jailbreak',
    0x351EC12: 'isDebugged',
    0x359DC87: 'isJailBroken',
    0x356763A: 'Jailbreak test string',
    0x359DBE6: '/Applications/Cydia.app',
    0x351E973: 'frida-server',
    0x351E651: 'cydia://',
    0x351E7A9: 'MobileSubstrate',
}

# also find CFString entries that reference these strings
# __cfstring at 0x03D087E0, each entry is 32 bytes:
# isa(8) + flags(8) + ptr(8) + length(8)
print('[*] scanning __cfstring for JB string wrappers...')
cfstring_off = 0x03D087E0
cfstring_size = 0x00069C00
cfstring_targets = {}

for off in range(cfstring_off, cfstring_off + cfstring_size, 32):
    if off + 32 > size:
        break
    isa, flags, ptr, length = struct.unpack_from('<QQQQ', data, off)
    if ptr in targets:
        name = targets[ptr]
        cfstring_targets[off] = name
        print(f'  CFString @ 0x{off:X} -> "{name}" (ptr=0x{ptr:X} len={length})')

# add cfstring addresses as additional targets
all_targets = dict(targets)
all_targets.update(cfstring_targets)

print(f'\n[*] {len(all_targets)} total target addresses')
print('[*] scanning {:.1f} MB of code...'.format(sum(s for _, s, _, _ in code_ranges) / 1024 / 1024))

hits = []

for code_off, code_size, code_vma, sect_name in code_ranges:
    code_end = code_off + code_size
    count = 0
    
    for off in range(code_off, min(code_end, size - 8), 4):
        instr = struct.unpack_from('<I', data, off)[0]
        
        # ADRP check
        if (instr & 0x9F000000) != 0x90000000:
            continue
        
        rd = instr & 0x1F
        immhi = (instr >> 5) & 0x7FFFF
        immlo = (instr >> 29) & 0x3
        imm = (immhi << 2) | immlo
        if imm & (1 << 20):
            imm -= (1 << 21)
        
        pc_vma = code_vma + (off - code_off)
        page_base = (pc_vma & ~0xFFF) + (imm << 12)
        
        # check next 1-3 instructions for ADD/LDR that complete the address
        for delta in range(1, 4):
            noff = off + delta * 4
            if noff >= size - 4:
                break
            ni = struct.unpack_from('<I', data, noff)[0]
            
            target = None
            
            # ADD Xd, Xn, #imm12 (no shift)
            if (ni & 0xFFC00000) == 0x91000000:
                rn = (ni >> 5) & 0x1F
                add_imm = (ni >> 10) & 0xFFF
                if rn == rd:
                    target = page_base + add_imm
            
            # LDR Xt, [Xn, #imm] (64-bit)
            elif (ni & 0xFFC00000) == 0xF9400000:
                rn = (ni >> 5) & 0x1F
                ldr_imm = ((ni >> 10) & 0xFFF) << 3
                if rn == rd:
                    target = page_base + ldr_imm
            
            # LDR Wt, [Xn, #imm] (32-bit)
            elif (ni & 0xFFC00000) == 0xB9400000:
                rn = (ni >> 5) & 0x1F
                ldr_imm = ((ni >> 10) & 0xFFF) << 2
                if rn == rd:
                    target = page_base + ldr_imm
            
            if target is not None and target in all_targets:
                name = all_targets[target]
                hits.append((off, noff, pc_vma, name))
                count += 1
                break
    
    print(f'  {sect_name}: {count} hits')

print(f'\n[*] total xrefs found: {len(hits)}')

if not hits:
    print('\n[!] no ADRP-based references found — trying B/BL scan near SVC...')
    # last resort: find functions containing the SVC #0x80 syscalls
    # and look at the context
    svc_locs = [0x6238, 0x3827252, 0x3869E02]
    for svc in svc_locs:
        print(f'\n  SVC at 0x{svc:X}, context:')
        # scan back for function prologue
        for back in range(0, 2048, 4):
            check = svc - back
            if check < 0:
                break
            ins = struct.unpack_from('<I', data, check)[0]
            # STP with X29, X30
            rt = ins & 0x1F
            rt2 = (ins >> 10) & 0x1F
            rn = (ins >> 5) & 0x1F
            if rt == 29 and rt2 == 30 and rn == 31:
                if (ins & 0xFE000000) == 0xA9000000:
                    print(f'    prologue at 0x{check:X} (STP X29,X30 - {back} bytes before SVC)')
                    # show function bytes
                    for j in range(0, min(back + 16, 200), 4):
                        inst = struct.unpack_from('<I', data, check + j)[0]
                        marker = ' <-- SVC' if check + j == svc else ''
                        print(f'      0x{check+j:08X}: {inst:08X}{marker}')
                    break
    
    # also try direct string search near code boundaries
    # the ios_jailbreak strings are at 0x351E*, which is in __cstring
    # Unity/IL2CPP might reference them via GOT or literal tables
    
    # check if there are pointers in __DATA.__const or __DATA.__data to these strings
    print('\n[*] scanning __DATA for pointer references to JB strings...')
    data_ranges = [
        (0x03930A30, 0x003D7DB0, '__DATA.__const'),
        (0x03EFF550, 0x002ADF2C, '__DATA.__data'),
    ]
    
    ptr_hits = []
    for d_off, d_size, d_name in data_ranges:
        for off in range(d_off, min(d_off + d_size, size - 8), 8):
            ptr = struct.unpack_from('<Q', data, off)[0]
            if ptr in targets:
                name = targets[ptr]
                ptr_hits.append((off, ptr, name))
                print(f'  [PTR] 0x{off:X} -> 0x{ptr:X} "{name}" ({d_name})')
    
    if ptr_hits:
        print(f'\n[*] found {len(ptr_hits)} pointer refs — now finding code that reads these pointers...')
        # these pointer addresses themselves become ADRP targets
        for ptr_off, ptr_val, ptr_name in ptr_hits:
            print(f'  scanning for code refs to pointer at 0x{ptr_off:X} ({ptr_name})...')
            ptr_page = ptr_off & ~0xFFF
            ptr_pageoff = ptr_off & 0xFFF
            
            # quick check: scan for ADRP that lands on this page
            for code_off2, code_size2, code_vma2, sect_name2 in code_ranges:
                for off in range(code_off2, min(code_off2 + code_size2, size - 8), 4):
                    instr = struct.unpack_from('<I', data, off)[0]
                    if (instr & 0x9F000000) != 0x90000000:
                        continue
                    
                    rd = instr & 0x1F
                    immhi = (instr >> 5) & 0x7FFFF
                    immlo = (instr >> 29) & 0x3
                    imm = (immhi << 2) | immlo
                    if imm & (1 << 20):
                        imm -= (1 << 21)
                    
                    pc_vma3 = code_vma2 + (off - code_off2)
                    page_base = (pc_vma3 & ~0xFFF) + (imm << 12)
                    
                    if page_base == ptr_page:
                        # check next instruction loads from ptr_pageoff
                        ni = struct.unpack_from('<I', data, off + 4)[0]
                        if (ni & 0xFFC00000) == 0xF9400000:
                            ldr_rn = (ni >> 5) & 0x1F
                            ldr_imm = ((ni >> 10) & 0xFFF) << 3
                            if ldr_rn == rd and ldr_imm == ptr_pageoff:
                                hits.append((off, off + 4, pc_vma3, ptr_name))
                                print(f'    [XREF] code at 0x{off:X} -> ptr @ 0x{ptr_off:X} -> "{ptr_name}"')

# find function prologues for all hits
print(f'\n[*] tracing {len(hits)} refs to function prologues...')

func_map = {}
for ref_off, ref_end, ref_vma, ref_name in hits:
    for back in range(0, 8192, 4):
        check = ref_off - back
        if check < 0:
            break
        ins = struct.unpack_from('<I', data, check)[0]
        rt = ins & 0x1F
        rt2 = (ins >> 10) & 0x1F
        rn = (ins >> 5) & 0x1F
        
        is_stp = (ins & 0xFE000000) == 0xA9000000 and rt == 29 and rt2 == 30 and rn == 31
        is_pacibsp = ins == 0xD503237F
        is_sub_sp = (ins & 0xFF0003FF) == 0xD100001F  # SUB SP, SP, #imm
        
        if is_stp or is_pacibsp:
            if check not in func_map:
                func_map[check] = []
            func_map[check].append(ref_name)
            break

print(f'\n[*] {len(func_map)} functions to patch')
print()
print('=' * 70)
print(' FINAL PATCH TABLE')
print('=' * 70)
for foff in sorted(func_map.keys()):
    refs = func_map[foff]
    fb = ' '.join(f'{data[foff+i]:02X}' for i in range(8))
    print(f'  0x{foff:08X}: {fb}  <- {", ".join(set(refs))}')
    print(f'    -> write: 00 00 80 52 C0 03 5F D6  (MOV W0,#0 + RET)')
print()
