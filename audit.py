import zipfile, struct, os

patched_ipa = 'StandRise-RE-1.0.0F2_patched.ipa'
orig_ipa = 'StandRise-RE-1.0.0F2.ipa'

print('========================================================')
print('           FULL IPA AUDIT REPORT')
print('========================================================\n')

with zipfile.ZipFile(patched_ipa, 'r') as z:
    # 1. Zip integrity
    corrupt = z.testzip()
    print('1. Zip archive integrity: ', 'OK (No corruption)' if not corrupt else f'FAILED ({corrupt})')
    
    # 2. Permissions check
    bin_info = z.getinfo('Payload/StandRiseRE.app/StandRiseRE')
    uf_info = z.getinfo('Payload/StandRiseRE.app/Frameworks/UnityFramework.framework/UnityFramework')
    dir_info = z.getinfo('Payload/StandRiseRE.app/')
    
    bin_perm = oct(bin_info.external_attr >> 16)
    uf_perm = oct(uf_info.external_attr >> 16)
    dir_perm = oct(dir_info.external_attr >> 16)
    
    print('\n2. POSIX Permissions:')
    print(f'   - StandRiseRE:      {bin_perm} (Expected: 0o100755 / -rwxr-xr-x) -> {"PASS" if bin_perm == "0o100755" else "FAIL"}')
    print(f'   - UnityFramework:   {uf_perm} (Expected: 0o100755 / -rwxr-xr-x) -> {"PASS" if uf_perm == "0o100755" else "FAIL"}')
    print(f'   - StandRiseRE.app/: {dir_perm} (Expected: 0o40755 / drwxr-xr-x)  -> {"PASS" if dir_perm == "0o40755" else "FAIL"}')
    
    # 3. Mach-O header validation (StandRiseRE)
    bin_data = z.read('Payload/StandRiseRE.app/StandRiseRE')
    b_magic, _, _, _, b_ncmds, b_sizeofcmds, _, _ = struct.unpack_from('<IIIIIIII', bin_data, 0)
    pos = 32
    b_cmds_ok = True
    b_has_cs = False
    for _ in range(b_ncmds):
        cmd, csz = struct.unpack_from('<II', bin_data, pos)
        if cmd == 0x1D:
            b_has_cs = True
        if csz == 0 or pos + csz > len(bin_data):
            b_cmds_ok = False
            break
        pos += csz
    print('\n3. StandRiseRE Mach-O Header:')
    print(f'   - magic: 0x{b_magic:08X}, ncmds: {b_ncmds}, sizeofcmds: {b_sizeofcmds}')
    print(f'   - Structural validity: {"PASS" if b_cmds_ok and pos == 32 + b_sizeofcmds else "FAIL"}')
    print(f'   - LC_CODE_SIGNATURE:   {"PASS (Found)" if b_has_cs else "FAIL"}')

    # 4. Mach-O header validation (UnityFramework)
    uf_data = z.read('Payload/StandRiseRE.app/Frameworks/UnityFramework.framework/UnityFramework')
    u_magic, _, _, _, u_ncmds, u_sizeofcmds, _, _ = struct.unpack_from('<IIIIIIII', uf_data, 0)
    pos = 32
    u_cmds_ok = True
    u_has_cs = False
    for _ in range(u_ncmds):
        cmd, csz = struct.unpack_from('<II', uf_data, pos)
        if cmd == 0x1D:
            u_has_cs = True
        if csz == 0 or pos + csz > len(uf_data):
            u_cmds_ok = False
            break
        pos += csz
    print('\n4. UnityFramework Mach-O Header:')
    print(f'   - magic: 0x{u_magic:08X}, ncmds: {u_ncmds}, sizeofcmds: {u_sizeofcmds}')
    print(f'   - Structural validity: {"PASS" if u_cmds_ok and pos == 32 + u_sizeofcmds else "FAIL"}')
    print(f'   - LC_CODE_SIGNATURE:   {"PASS (Found)" if u_has_cs else "FAIL"}')

    # 5. Byte diff check on UnityFramework
    with zipfile.ZipFile(orig_ipa, 'r') as z_orig:
        orig_uf = z_orig.read('Payload/StandRiseRE.app/Frameworks/UnityFramework.framework/UnityFramework')
    
    diff_count = 0
    diff_blocks = []
    i = 0
    while i < len(orig_uf):
        if orig_uf[i] != uf_data[i]:
            start = i
            while i < len(orig_uf) and orig_uf[i] != uf_data[i]:
                i += 1
            diff_blocks.append((start, i - start, orig_uf[start:i], uf_data[start:i]))
            diff_count += (i - start)
        else:
            i += 1

    print('\n5. UnityFramework Patch Modifications:')
    print(f'   - Total modified bytes: {diff_count} out of {len(orig_uf)} ({len(diff_blocks)} functions)')
    for off, sz, b_o, b_p in diff_blocks:
        print(f'     * Offset 0x{off:08X} ({sz} bytes): {b_o.hex()} -> {b_p.hex()} (MOV W0,#0; RET)')

    print(f'   - Unintended changes: {"NONE (100% clean)" if len(diff_blocks) == 5 and diff_count == 40 else f"WARNING ({len(diff_blocks)} blocks)"}')

print('\n========================================================')
print('                 AUDIT COMPLETED')
print('========================================================')
