import zipfile, os, sys, time

IPA = r"C:\Users\accountmanager\Desktop\native\ProjectRise-1.0.ipa"
OUT = r"C:\Users\accountmanager\Desktop\native\dump"


def safe(p):
    # long-path support on Windows
    p = os.path.abspath(p)
    if not p.startswith("\\\\?\\"):
        p = "\\\\?\\" + p
    return p


os.makedirs(safe(OUT), exist_ok=True)
z = zipfile.ZipFile(IPA)
infos = z.infolist()
total = len(infos)
written = 0
skipped = 0
t0 = time.time()

for i, info in enumerate(infos):
    name = info.filename
    rel = name.replace("Payload/", "", 1)
    if not rel:
        continue
    dst = os.path.join(OUT, *rel.split("/"))
    if name.endswith("/"):
        os.makedirs(safe(dst), exist_ok=True)
        continue
    if os.path.exists(dst) and os.path.getsize(dst) == info.file_size:
        skipped += 1
        continue
    os.makedirs(safe(os.path.dirname(dst)), exist_ok=True)
    with z.open(info) as src, open(safe(dst), "wb") as f:
        while True:
            chunk = src.read(1 << 22)
            if not chunk:
                break
            f.write(chunk)
    written += 1
    if (i % 25) == 0:
        print(f"[{i+1}/{total}] {rel[:90]}", flush=True)

print(f"\nDONE: written={written} skipped={skipped} total={total} in {time.time()-t0:.1f}s")