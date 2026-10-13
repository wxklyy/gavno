import re, sys, collections

path = sys.argv[1]
lines = open(path, encoding="utf-8", errors="replace").read().splitlines()

PATTERNS = {
    "anticheat_core": r"(?i)anticheat|anti[-_ ]?cheat|antihack|anti[-_ ]?hack|cheatengine|cheat detect|speedhack|speed hack|aimbot|wallhack|wh\.|esp\b|triggerbot|recoil",
    "integrity": r"(?i)integrity|checksum|crc32|hashcheck|verify.*file|file.*verif|signature check|tamper|corrupt",
    "jailbreak": r"(?i)jailbreak|jail broken|cydia|substrate|frida|checkra1n|unc0ver|sileo|tweak|mobilesubstrate|substitute|ellekit|rootless",
    "debugger": r"(?i)ptrace|PT_DENY_ATTACH|debugger|sysctl|isdebuggerpresent|am being debugged|lldb|gdb|debugserver",
    "vpn_proxy": r"(?i)vpn|proxy detected|tun0|ppp0|ipsec",
    "emulator": r"(?i)emulator|simulator",
    "report_ban": r"(?i)reportplayer|report player|ban player|banuser|kick player|vote.?kick|cheat report|sendreport",
    "vac_like": r"(?i)\bVAC\b|battleye|easyanticheat|easy anti|eac\b|fairfight|denuvo|xigncode|nprotect|gameguard|hackshield|mhyprot|ace[-_ ]?guard|tp\.dll|tencent.*protect|netease",
    "memory_scan": r"(?i)memory scan|scan memory|pattern scan|aob scan|readprocessmemory|mach_vm_read|vm_read|task_for_pid",
    "hook_detect": r"(?i)hook detect|detour|inline hook|fishhook|method swizzl|swizzle|dlopen|dlsym|mach_msg|injected dylib|DYLD_INSERT",
}

for label, pat in PATTERNS.items():
    rx = re.compile(pat)
    hits = [l for l in lines if rx.search(l)]
    uniq = list(dict.fromkeys(hits))
    print(f"\n########## {label}: {len(uniq)} unique hits ##########")
    for h in uniq[:120]:
        print("   ", h[:300])