#!/usr/bin/env python3
"""Idempotently add the opt-in Teamspace app factory to the pinned Octop source.

Usage: python app/deployment/patch_octop.py upstream/Octop
No code is copied out of the immutable review archive; run this only against the
development copy used for the deployment. Restoring the original is supported.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

SOURCE_COMMIT = "dd9dce470844c25d59effb50615bb3c667ea25cd"
SOURCE_SHA256 = "58a1cb9715f1239ef0e6044de731d3c7b9eec9f5533d690eca74d01d5fc8ecdf"

ANCHOR = "def build_app(server: OctopServer) -> FastAPI:\n"
HOOK = (
    ANCHOR
    + '    # TEAMSPACE_FACTORY_V1 — local opt-in collaboration integration.\n'
    + '    import os\n\n'
    + '    if os.environ.get("OCTOP_TEAMSPACE") == "1":\n'
    + '        from teamspace.integration import build_team_app\n\n'
    + '        return build_team_app(server)\n\n'
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("octop_root", type=Path)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    target = args.octop_root.resolve() / "src/octop/api/app.py"
    original = target.read_bytes().decode("utf-8")
    clean = original.replace(HOOK, ANCHOR, 1) if HOOK in original else original
    if hashlib.sha256(clean.encode("utf-8")).hexdigest() != SOURCE_SHA256:
        raise SystemExit(
            "Octop app.py does not match reviewed commit " + SOURCE_COMMIT
            + "; refusing to patch or restore an unreviewed version"
        )
    if args.restore:
        if HOOK not in original:
            raise SystemExit("Expected Teamspace hook not found; refusing an ambiguous restore")
        updated = original.replace(HOOK, ANCHOR, 1)
    else:
        if HOOK in original:
            print("Teamspace hook already installed")
            return
        if "TEAMSPACE_FACTORY" in original or original.count(ANCHOR) != 1:
            raise SystemExit("Octop app factory differs from the reviewed source; manual review required")
        updated = original.replace(ANCHOR, HOOK, 1)
    compile(updated, str(target), "exec")
    target.write_bytes(updated.encode("utf-8"))
    print("Restored original app factory" if args.restore else "Installed opt-in Teamspace app factory")
    print("File:", target)
    print("SHA256:", hashlib.sha256(updated.encode()).hexdigest())


if __name__ == "__main__":
    main()
