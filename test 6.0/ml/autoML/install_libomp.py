"""Extract a verified Homebrew OpenMP library locally, without installing globally."""

import hashlib
import io
import json
from pathlib import Path
import platform
import tarfile
import urllib.request

if platform.system() != "Darwin" or platform.machine() != "arm64":
    raise SystemExit("This helper is for macOS arm64 only")

root = Path(__file__).resolve().parent / ".cache/libomp"
formula_url = "https://formulae.brew.sh/api/formula/libomp.json"
formula = json.load(urllib.request.urlopen(formula_url))
tag = "arm64_sequoia"
bottle = formula["bottle"]["stable"]["files"][tag]
token_url = "https://ghcr.io/token?service=ghcr.io&scope=repository:homebrew/core/libomp:pull"
token = json.load(urllib.request.urlopen(token_url))["token"]
request = urllib.request.Request(bottle["url"], headers={"Authorization": f"Bearer {token}"})
archive = urllib.request.urlopen(request).read()
if hashlib.sha256(archive).hexdigest() != bottle["sha256"]:
    raise SystemExit("OpenMP bottle checksum mismatch")
root.mkdir(parents=True, exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
    members = [m for m in tar.getmembers() if m.isfile() and m.name.endswith("/lib/libomp.dylib")]
    if len(members) != 1:
        raise SystemExit("Expected exactly one libomp.dylib")
    (root / "libomp.dylib").write_bytes(tar.extractfile(members[0]).read())
provenance = {"formula": formula_url, "version": formula["versions"]["stable"],
              "tag": tag, "bottle_url": bottle["url"], "bottle_sha256": bottle["sha256"],
              "library_sha256": hashlib.sha256((root / "libomp.dylib").read_bytes()).hexdigest()}
(root / "source.json").write_text(json.dumps(provenance, indent=2) + "\n")
print(root)
