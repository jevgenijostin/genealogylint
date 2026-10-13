import argparse
import json
import os
import sys
from .license import enforce
from .parser import load
from .relationships import relate
from .validation import validate


def main(argv=None):
    parser = argparse.ArgumentParser(prog="genealogylint")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate", help="Validate one tree, or multiple with --batch")
    check.add_argument("files", nargs="+")
    check.add_argument("--json", action="store_true")
    check.add_argument("--batch", action="store_true")
    check.add_argument("--min-parent-age", type=int, default=12)
    check.add_argument("--max-parent-age", type=int, default=75)
    check.add_argument("--max-death-age", type=int, default=120)
    relation = commands.add_parser("relate", help="Describe id1's relationship to id2")
    relation.add_argument("file")
    relation.add_argument("id1")
    relation.add_argument("id2")
    for command in (check, relation):
        command.add_argument("--license-key", default=os.environ.get("GENEALOGYLINT_LICENSE", ""))
    args = parser.parse_args(argv)
    try:
        if args.command == "relate":
            tree = load(args.file)
            enforce(len(tree.people), args.license_key)
            print(relate(tree, args.id1, args.id2))
            return 0
        if len(args.files) > 1 and not args.batch:
            raise ValueError("Multiple files require --batch")
        reports = []
        for file in args.files:
            tree = load(file)
            enforce(len(tree.people), args.license_key, args.batch)
            findings = validate(tree, args.min_parent_age, args.max_parent_age, args.max_death_age)
            reports.append({"file": file, "individual_count": len(tree.people), "findings": [f.to_dict() for f in findings]})
        if args.json:
            print(json.dumps(reports if args.batch else reports[0], indent=2))
        else:
            for report in reports:
                print(f"{report['file']}: {report['individual_count']} individuals, {len(report['findings'])} findings")
                print(f"{'SEVERITY':8} {'CHECK':23} {'IDS':24} MESSAGE")
                for f in report["findings"]:
                    print(f"{f['severity']:8} {f['code']:23} {', '.join(f['ids']):24} {f['message']}")
        return 1 if any(f['severity'] == 'ERROR' for r in reports for f in r['findings']) else 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"genealogylint: {exc}", file=sys.stderr)
        return 2
