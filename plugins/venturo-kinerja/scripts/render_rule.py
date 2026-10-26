#!/usr/bin/env python3
"""Tampilkan rule kinerja dengan placeholder sudah dirender.

    render_rule.py workflow quality-score/structural   # isi rule, placeholder dirender
    render_rule.py --list                              # slug, versi, tipe, deskripsi
    render_rule.py --thresholds                        # ambang structural (JSON)
    render_rule.py --stack-for PATH                    # slug skill stack yang cocok untuk repo

Placeholder dirender seperti skills.substituteTemplates() di kinerja-be:
{{SEVERITY_PENALTIES}} dari angka reviewscore, {{SEVERITY_SCOPE}} dan
{{VERDICT_MEDIUM_RULE}} dengan default setting kinerja (Medium aktif).
"""

import argparse
import json
import os
import sys

import kinerja_lib as lib

# Penanda stack mengikuti deskripsi context "Skill stack ..." (dynamic).
STACK_MARKERS = [
    ("golang", ["go.mod"]),
    ("php", ["composer.json"]),
    ("flutter", ["pubspec.yaml"]),
]


def stack_slugs(repo):
    found = [slug for slug, markers in STACK_MARKERS
             if any(os.path.isfile(os.path.join(repo, m)) for m in markers)]
    pkg = os.path.join(repo, "package.json")
    if os.path.isfile(pkg):
        with open(pkg, encoding="utf-8", errors="replace") as fh:
            deps = fh.read()
        if '"react-native"' in deps:
            found.append("react-native")
        elif '"react"' in deps:
            found.append("react")
        else:
            found.append("node")
    return found


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("slugs", nargs="*")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--thresholds", action="store_true")
    ap.add_argument("--stack-for", metavar="PATH")
    ap.add_argument("--raw", action="store_true", help="tanpa render placeholder")
    args = ap.parse_args(argv)
    if args.list:
        with open(os.path.join(lib.RULES_DIR, "rules.lock.json"), encoding="utf-8") as fh:
            for c in json.load(fh)["contexts"]:
                print("%-26s v%-3d %-10s %s" % (c["slug"], c["version"], c["skill_type"], c["description"]))
        return 0
    if args.thresholds:
        print(json.dumps(lib.structural_thresholds(), indent=2))
        return 0
    if args.stack_for:
        print("\n".join(stack_slugs(args.stack_for)))
        return 0
    if not args.slugs:
        ap.error("sebutkan slug, atau --list / --thresholds / --stack-for")
    for i, slug in enumerate(args.slugs):
        try:
            text = lib.read_rule(slug, render=not args.raw)
        except OSError:
            print("render_rule: slug %r tidak ada di rules/ (lihat --list)" % slug, file=sys.stderr)
            return 2
        print(("\n\n" if i else "") + "<!-- rules/%s.md -->\n%s" % (slug, text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
