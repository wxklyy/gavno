"""
S2Rise Offset Dumper v2
Broader search — dumps ALL types in Assembly-CSharp that have
player/game/weapon/health related fields or methods.
"""

import struct
import sys
import json
import re

META_PATH = r"C:\Users\accountmanager\Desktop\native\_analysis\extracted\Data__Managed__Metadata__global-metadata.dat"

data = open(META_PATH, "rb").read()

magic, version = struct.unpack_from("<II", data, 0)
print(f"Metadata v{version}, size={len(data)}")

pairs = []
for i in range(29):
    off, size = struct.unpack_from("<II", data, 8 + i * 8)
    pairs.append((off, size))

str_off, str_size = pairs[2]
mtd_off, mtd_size = pairs[5]
fld_off, fld_size = pairs[11]
td_off, td_size = pairs[19]
img_off, img_size = pairs[20]

region = data[str_off:str_off + str_size]

def get_str(o):
    if o < 0 or o >= str_size:
        return f"<bad:{o}>"
    end = region.find(b"\x00", o)
    if end < 0:
        end = o + 256
    return region[o:end].decode("utf-8", "replace")

IMG = 40
n_img = img_size // IMG
images = {}
for i in range(n_img):
    base = img_off + i * IMG
    name = get_str(struct.unpack_from("<I", data, base)[0])
    ts, tc = struct.unpack_from("<II", data, base + 8)
    images[name] = (ts, ts + tc)

asm_csharp_range = images.get("Assembly-CSharp.dll", (0, 0))
print(f"Assembly-CSharp.dll types: {asm_csharp_range[0]}..{asm_csharp_range[1]}")

TD = 88
n_td = td_size // TD
MTD = 40
FLD = 12

# keywords to match in field/method names
field_keywords = re.compile(
    r"(?i)(health|isAlive|isDead|teamId|teamID|nickName|NickName|"
    r"isLocal|weapon|animator|transform|position|players|_players|"
    r"playerList|localPlayer|PlayerController|hitbox|Hitbox|"
    r"collider|damage|recoil|ammo|alive|head|bone|skeleton|"
    r"speed|aimTarget|crosshair|fov|camera|mainCamera|"
    r"playerData|playerInfo|playerState|isBot|isMine|"
    r"MaxHealth|maxHealth|currentHealth|armor)"
)

# also match in type names/namespaces  
type_keywords = re.compile(
    r"(?i)(PlayerController|PlayerManager|PlayerState|PlayerData|"
    r"PlayerInfo|PlayerHitbox|PlayerMovement|PlayerAim|"
    r"GameManager|MatchManager|RoundManager|"
    r"WeaponController|ShootController|BulletController|"
    r"Anticheat|AntiCheat|GameAntiCheat|"
    r"HitController|DamageController|HealthController|"
    r"SpectatorController|CameraController|"
    r"BoltPlayer|NetworkPlayer|PhotonPlayer)"
)

results = {}

for i in range(n_td):
    b = td_off + i * TD
    raw = data[b:b + TD]
    name_idx = struct.unpack_from("<I", raw, 0)[0]
    ns_idx = struct.unpack_from("<I", raw, 4)[0]
    
    name = get_str(name_idx)
    ns = get_str(ns_idx)
    full = f"{ns}.{name}" if ns else name
    
    field_start, method_start = struct.unpack_from("<ii", raw, 36)
    counts = struct.unpack_from("<8H", raw, 68)
    method_count = counts[0]
    field_count = counts[2]
    
    # check type name match
    type_match = bool(type_keywords.search(full))
    
    # check field names
    field_match = False
    fields = []
    for j in range(field_count):
        if field_start < 0:
            break
        fo = fld_off + (field_start + j) * FLD
        if fo + FLD > len(data):
            break
        fnidx, ftidx = struct.unpack_from("<II", data, fo)
        fname = get_str(fnidx)
        fields.append({"name": fname, "typeIndex": ftidx, "fieldIndex": field_start + j})
        if field_keywords.search(fname):
            field_match = True
    
    # only process if in Assembly-CSharp range or matched
    in_asm = asm_csharp_range[0] <= i < asm_csharp_range[1]
    
    if (type_match or field_match) and in_asm:
        methods = []
        for j in range(method_count):
            if method_start < 0:
                break
            mo = mtd_off + (method_start + j) * MTD
            if mo + MTD > len(data):
                break
            mnidx = struct.unpack_from("<I", data, mo)[0]
            param_count = struct.unpack_from("<H", data, mo + 38)[0]
            token = struct.unpack_from("<I", data, mo + 24)[0]
            mname = get_str(mnidx)
            methods.append({"name": mname, "paramCount": param_count, 
                           "methodIndex": method_start + j, "token": hex(token)})
        
        results[i] = {
            "typeIndex": i,
            "fullName": full,
            "name": name,
            "namespace": ns,
            "fieldCount": field_count,
            "methodCount": method_count,
            "fields": fields,
            "methods": methods,
        }

print(f"\nFound {len(results)} matching types in Assembly-CSharp\n")
print("=" * 80)

for idx in sorted(results.keys()):
    t = results[idx]
    print(f"\n### [{t['typeIndex']}] {t['fullName']}")
    
    if t["fields"]:
        print(f"  FIELDS ({len(t['fields'])}):")
        for f in t["fields"]:
            marker = " <<<" if field_keywords.search(f["name"]) else ""
            print(f"    [{f['fieldIndex']:5d}] {f['name']:45s} type={f['typeIndex']}{marker}")
    
    if t["methods"]:
        print(f"  METHODS ({len(t['methods'])}):")
        for m in t["methods"]:
            marker = " <<<" if field_keywords.search(m["name"]) else ""
            print(f"    [{m['methodIndex']:5d}] {m['name']:45s} params={m['paramCount']}{marker}")

# save
out = r"C:\Users\accountmanager\Desktop\native\_analysis\offsets_v2.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False, default=str)
print(f"\nSaved to {out}")
