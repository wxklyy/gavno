import re, sys, os

MIN = 5
pat = re.compile(rb"[\x20-\x7e]{%d,}" % MIN)


def strings(path):
    data = open(path, "rb").read()
    out = []
    for m in pat.finditer(data):
        out.append(m.group().decode("ascii"))
    return out


if __name__ == "__main__":
    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else None
    s = strings(path)
    print("total strings:", len(s))
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(s))
        print("written:", out)