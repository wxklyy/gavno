import zipfile, os

IPA = r"C:\Users\accountmanager\Desktop\native\ProjectRise-1.0.ipa"
OUT = r"C:\Users\accountmanager\Desktop\native\_analysis\extracted"

WANT_EXACT = {
    "Payload/standoff2.app/Info.plist",
    "Payload/standoff2.app/PkgInfo",
    "Payload/standoff2.app/standoff2",
    "Payload/standoff2.app/SC_Info/Manifest.plist",
    "Payload/standoff2.app/Frameworks/UnityFramework.framework/UnityFramework",
    "Payload/standoff2.app/Frameworks/UnityFramework.framework/Info.plist",
    "Payload/standoff2.app/Data/Managed/Metadata/global-metadata.dat",
}

os.makedirs(OUT, exist_ok=True)
z = zipfile.ZipFile(IPA)
names = set(z.namelist())

for n in sorted(WANT_EXACT):
    if n in names:
        dst = os.path.join(OUT, n.replace("Payload/standoff2.app/", "").replace("/", "__"))
        with z.open(n) as src, open(dst, "wb") as f:
            while True:
                chunk = src.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        print("extracted:", n, "->", os.path.basename(dst), os.path.getsize(dst))
    else:
        print("MISSING:", n)

print("\n=== Data/Managed assemblies ===")
for n in sorted(names):
    if "/Data/Managed/" in n and n.endswith(".dll"):
        print(" ", n.split("/Data/Managed/")[-1])

print("\n=== Frameworks ===")
for n in sorted(names):
    if "/Frameworks/" in n and n.count("/") == 3:
        print(" ", n)