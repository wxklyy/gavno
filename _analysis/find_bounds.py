import struct

with open(r'_analysis\extracted\Frameworks__UnityFramework.framework__UnityFramework', 'rb') as f:
    data = f.read()

# scan the cluster region 0x142E74 - 0x143F00 for all functions
# a function = starts after a RET, ends at next RET

print('=== ALL FUNCTIONS IN JB DETECTION CLUSTER ===')
print('    range: 0x142E74 - 0x144000')
print()

functions = []
off = 0x142E74
end_region = 0x144000

while off < end_region:
    ins = struct.unpack_from('<I', data, off)[0]
    # find next RET
    func_start = off
    func_end = None
    for fwd in range(0, 8192, 4):
        check = func_start + fwd
        if check >= len(data) - 4:
            break
        ei = struct.unpack_from('<I', data, check)[0]
        if ei == 0xD65F03C0 and fwd > 0:
            func_end = check
            break
    
    if func_end is None:
        break
    
    func_size = func_end - func_start + 4
    
    # check if it contains ADRP to any of our target pages
    has_jb_ref = False
    ref_details = []
    for i in range(func_start, func_end + 4, 4):
        ins2 = struct.unpack_from('<I', data, i)[0]
        if (ins2 & 0x9F000000) == 0x90000000:
            immhi = (ins2 >> 5) & 0x7FFFF
            immlo = (ins2 >> 29) & 0x3
            imm = (immhi << 2) | immlo
            if imm & (1 << 20):
                imm -= (1 << 21)
            page = (i & ~0xFFF) + (imm << 12)
            if page in (0x351E000, 0x359D000, 0x3567000):
                has_jb_ref = True
                # check next for ADD to see exact target
                if i + 4 <= func_end:
                    ni = struct.unpack_from('<I', data, i+4)[0]
                    if (ni & 0xFFC00000) == 0x91000000:
                        add_imm = (ni >> 10) & 0xFFF
                        target_addr = page + add_imm
                        # read the string at that address
                        try:
                            s = data[target_addr:target_addr+50].split(b'\x00')[0].decode('utf-8', errors='replace')
                        except:
                            s = '?'
                        ref_details.append(s)
    
    fb = ' '.join('%02X' % data[func_start+i] for i in range(min(8, func_size)))
    marker = ' ** JB **' if has_jb_ref else ''
    refs_str = (' -> ' + ', '.join(ref_details)) if ref_details else ''
    print('  0x%08X (%3d bytes): %s%s%s' % (func_start, func_size, fb, marker, refs_str))
    
    if has_jb_ref:
        functions.append((func_start, func_size, ref_details))
    
    off = func_end + 4

print()
print('=== FUNCTIONS TO PATCH (return false) ===')
print()
for func_start, func_size, refs in functions:
    print('  0x%08X (%d bytes) — %s' % (func_start, func_size, ', '.join(refs)))

# also check the bigger Cydia.app functions we found
extra_funcs = [
    (0x005CCA58, 288, ['/Applications/Cydia.app check (1)']),
    (0x0067A188, None, ['/Applications/Cydia.app check (2)']),
]

print()
print('=== ADDITIONAL PATCH TARGETS ===')
for func_start, func_size, refs in extra_funcs:
    sz_str = '%d bytes' % func_size if func_size else 'unknown size'
    print('  0x%08X (%s) — %s' % (func_start, sz_str, ', '.join(refs)))

# Final: the IL2CPP registration function
print()
print('=== IL2CPP REGISTRATION (isDebugged + ios_jailbreak) ===')
print('  0x017C7BA8 (452 bytes) — patch first 8 bytes to RET 0')
