#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RATIFY - Constitutional ratification hashing tool for the Governed AI Organism corpus.

Commands:
  manifest [--exclude a.docx,b.docx]
             Recompute canonical SHA-256 hashes of all *.docx in this folder (minus any
             listed as excluded) and write ratification_manifest.json (with a Merkle-style
             corpus root). Excluded names are stored in the manifest and skipped by
             verify/seal, so operational documents may live in the corpus folder without
             perturbing the ratified root.
  verify     Recompute hashes and compare against the manifest. Exit 1 on any mismatch.
  seal       Require a clean verify, then write ratification_record.json sealing the
             corpus root hash. HMAC-SHA-256 signed when PARAGON_SECURITY_SIGNING_KEY
             is set; otherwise the signature slot is recorded as PENDING.

Canonicalization: all body paragraphs (in document order) plus table rows (cells joined
by ' | ', merged/duplicate cells deduplicated). This is deterministic across runs and
independent of docx zip internals, so Word re-saves do not silently break the chain.
"""
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

BASE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = "ratification_manifest.json"
RECORD = "ratification_record.json"
PRINCIPAL = "jon"
ALG = "sha256"


def _block_iter(parent):
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl

    for child in parent.element.body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def _cell_lines(cell):
    return [ln.strip() for ln in cell.text.splitlines() if ln.strip()]


def canonical_text(path):
    doc = Document(path)
    lines = []
    for block in _block_iter(doc):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t:
                lines.append(t)
        else:
            for row in block.rows:
                cell_lines = []
                prev = None
                for cell in row.cells:
                    joined = "\n".join(_cell_lines(cell))
                    if joined != prev:
                        cell_lines.append(joined)
                    prev = joined
                lines.append(" | ".join(cell_lines))
    return "\n".join(lines)


def doc_hashes(excludes=()):
    out = {}
    for name in sorted(os.listdir(BASE)):
        if not name.lower().endswith(".docx"):
            continue
        if name in excludes:
            continue
        path = os.path.join(BASE, name)
        text = canonical_text(path)
        out[name] = {
            "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "chars": len(text),
            "path": path,
        }
    return out


def merkle_root(hashes):
    joined = "\n".join("%s:%s" % (n, h["sha256"]) for n, h in sorted(hashes.items()))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _manifest_path():
    return os.path.join(BASE, MANIFEST)


def _record_path():
    return os.path.join(BASE, RECORD)


def cmd_manifest(excludes=()):
    hashes = doc_hashes(excludes=excludes)
    if not hashes:
        print("No .docx instruments found in", BASE)
        return 2
    root = merkle_root(hashes)
    manifest = {
        "manifest_version": "1.0",
        "principal": PRINCIPAL,
        "algorithm": ALG,
        "canonicalization": "body paragraphs + table rows, cells joined by ' | ', "
                            "duplicate/merged cells deduplicated, document order",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "instrument_count": len(hashes),
        "excluded_instruments": sorted(excludes),
        "merkle_root": root,
        "instruments": {n: {"sha256": h["sha256"], "chars": h["chars"]}
                        for n, h in sorted(hashes.items())},
    }
    with open(_manifest_path(), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    print("Manifest written: %s" % _manifest_path())
    print("Instruments: %d" % len(hashes))
    for n, h in sorted(hashes.items()):
        print("  %s  %s" % (h["sha256"][:16], n))
    for n in sorted(excludes):
        print("  (excluded)  %s" % n)
    print("MERKLE ROOT (corpus root of trust): %s" % root)
    return 0


def _recompute(excludes=()):
    return doc_hashes(excludes=excludes), merkle_root(doc_hashes(excludes=excludes))


def cmd_verify():
    if not os.path.exists(_manifest_path()):
        print("No manifest found. Run 'manifest' first.")
        return 2
    with open(_manifest_path(), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    excludes = set(manifest.get("excluded_instruments", ()))
    hashes, root = _recompute(excludes=excludes)
    ok = True
    for name in sorted(set(list(manifest["instruments"]) + list(hashes))):
        if name in excludes:
            presence = os.path.exists(os.path.join(BASE, name))
            print("SKIP  %s (operational exclude; present=%s)" % (name, presence))
            continue
        if name not in manifest["instruments"]:
            print("FAIL  new instrument not in manifest: %s" % name)
            ok = False
            continue
        if name not in hashes:
            print("FAIL  instrument missing: %s" % name)
            ok = False
            continue
        expected = manifest["instruments"][name]["sha256"]
        actual = hashes[name]["sha256"]
        if expected == actual:
            print("PASS  %s  %s" % (actual[:16], name))
        else:
            print("FAIL  %s expected=%s actual=%s" % (name, expected[:16], actual[:16]))
            ok = False
    if root != manifest.get("merkle_root"):
        print("FAIL  merkle root changed: expected=%s actual=%s"
              % (manifest.get("merkle_root"), root))
        ok = False
    else:
        print("PASS  merkle root %s" % root[:16])
    if not ok:
        print("VERIFY: FAILURE - corpus integrity is compromised.")
        return 1
    print("VERIFY: PASS - all instruments match the ratified manifest.")
    return 0


def cmd_seal():
    rc = cmd_verify()
    if rc != 0:
        print("Seal aborted: corpus did not verify clean.")
        return rc
    with open(_manifest_path(), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    root = manifest["merkle_root"]
    seed_sha = next((h["sha256"] for n, h in manifest["instruments"].items()
                     if n.lower().startswith("cdg seed")), "not-found")
    now = datetime.now(timezone.utc).isoformat()
    key = os.getenv("PARAGON_SECURITY_SIGNING_KEY")
    if key:
        signature = hmac.new(key.encode("utf-8"), root.encode("ascii"),
                             hashlib.sha256).hexdigest()
        sig_status = "HMAC-SHA-256_SIGNED"
    else:
        signature = "PENDING_PRIMARY_PRINCIPAL_SIGNATURE"
        sig_status = "PENDING"
    record = {
        "record_id": "REC-" + root[:12].upper(),
        "principal": PRINCIPAL,
        "instrument": "AI Organism constitutional corpus root of trust",
        "algorithm": ALG,
        "merkle_root": root,
        "cdg_seed_file_sha256": seed_sha,
        "signature": signature,
        "signature_status": sig_status,
        "sealed_at": now,
        "verified_at": now,
        "chain": "Every subsequent CDG version must be traceable to this root via the "
                 "unbroken hash chain in the Pattern Ledger (CDG Seed File §5.3; "
                 "Constitution Art. IX GOV-07).",
    }
    with open(_record_path(), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, sort_keys=True)
    print("Ratification record written: %s" % _record_path())
    print()
    print("### INSERT INTO CDG SEED FILE §5.3 ###")
    print("Algorithm: SHA-256")
    print("Hash (CDG Seed File content):  %s" % seed_sha)
    print("Hash Chain Root (full corpus):  %s" % root)
    print("Sealed By: %s (Primary Principal)" % PRINCIPAL)
    print("Signature: %s" % sig_status)
    print("### END INSERT ###")
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "manifest"
    args = sys.argv[2:]
    excludes = ()
    if "--exclude" in args:
        i = args.index("--exclude")
        if i + 1 < len(args):
            excludes = tuple(n.strip() for n in args[i + 1].split(",") if n.strip())
    if cmd == "manifest":
        return cmd_manifest(excludes=excludes)
    if cmd == "verify":
        return cmd_verify()
    if cmd == "seal":
        return cmd_seal()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())