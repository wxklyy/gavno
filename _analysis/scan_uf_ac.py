#!/usr/bin/env python3
"""scan UnityFramework for AC strings and find patchable offsets"""
import struct, os, sys

uf_path = r'_analysis\extracted\Frameworks__UnityFramework.framework__UnityFramework'
if not os.path.isfile(uf_path):
    print('[-] UnityFramework not found')
    sys.exit(1)

with open(uf_path, 'rb') as f:
    data = f.read()

print(f'[*] UnityFramework size: {len(data)} bytes ({len(data)/1024/1024:.1f} MB)')

patterns = [
    b'ios_jailbreak',
    b'isJailBroken',
    b'isDebugged',
    b'Jailbreak test string',
    b'/Applications/Cydia.app',
    b'frida-server',
    b'MobileSubstrate',
    b'cydia://',
    b'AntiCheatManager',
    b'GameAntiCheatManager',
    b'ReportViaServer',
    b'Aimbot cheat',
    b'Damage cheat',
    b'Wallhack',
    b'Injection cheat',
    b'cheat_activities',
    b'anticheat_enabled',
    b'hook_detect',
    b'LIBFRIDA',
    b'FridaGadget',
    b'PT_DENY_ATTACH',
    b'ptrace',
    b'_dyld_get_image_name',
]

print()
for p in patterns:
    locs = []
    start = 0
    while True:
        idx = data.find(p, start)
        if idx == -1:
            break
        locs.append(idx)
        start = idx + 1
    status = '+' if locs else '-'
    count = len(locs)
    addrs = ' '.join(f'0x{l:X}' for l in locs[:5])
    name = p.decode('utf-8', errors='replace')
    print(f'  [{status}] "{name}" -> {count}x @ {addrs}')

# also scan for ptrace(PT_DENY_ATTACH) ARM64 pattern
# MOV X0, #31 = 0xD28003E0
print()
print('[*] scanning for ptrace(PT_DENY_ATTACH) ARM64 pattern...')
ptrace_mov = struct.pack('<I', 0xD28003E0)  # MOV X0, #0x1F
locs = []
start = 0
while True:
    idx = data.find(ptrace_mov, start)
    if idx == -1:
        break
    locs.append(idx)
    start = idx + 1

print(f'  found MOV X0, #31 at {len(locs)} locations')
for loc in locs[:10]:
    # show context: 3 instructions before, this one, 3 after
    ctx_start = max(0, loc - 12)
    ctx_end = min(len(data), loc + 16)
    ctx = data[ctx_start:ctx_end]
    hex_str = ' '.join(f'{b:02X}' for b in ctx)
    print(f'    0x{loc:X}: {hex_str}')

# scan for SVC #0x80 (syscall) which is used by ptrace
print()
print('[*] scanning for SVC #0x80 (syscall)...')
svc_80 = struct.pack('<I', 0xD4001001)
locs = []
start = 0
while True:
    idx = data.find(svc_80, start)
    if idx == -1:
        break
    locs.append(idx)
    start = idx + 1
print(f'  found SVC #0x80 at {len(locs)} locations')
for loc in locs[:10]:
    print(f'    0x{loc:X}')
