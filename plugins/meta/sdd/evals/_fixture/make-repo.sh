#!/usr/bin/env bash
# Builds the eval fixture in the current directory: a tiny Python CLI ("tally") with unit
# tests, a bare origin next to it, and sdd initialised and pushed on main. Every case's
# scaffold.sh runs this, then adds its own twist. Runs as `bash <path>` in the case's cwd.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
sdd="$here/../../tools/sdd.py"
origin="$(dirname "$PWD")/origin.git"

git init -q --bare -b main "$origin"
git init -q -b main .
git remote add origin "$origin"
git config user.email >/dev/null || { git config user.name "sdd eval"; git config user.email eval@example.invalid; }

mkdir -p tally tests/unit tests/acceptance
touch tests/__init__.py tests/unit/__init__.py tests/acceptance/__init__.py

cat > tally/__init__.py <<'EOF'
"""tally: sum the numbers in a text file, one per line."""
EOF

cat > tally/core.py <<'EOF'
def parse(text):
    """One number per line."""
    return [float(line) for line in text.split("\n")]


def total(values):
    return sum(values)
EOF

cat > tally/__main__.py <<'EOF'
import sys

from tally.core import parse, total


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python3 -m tally FILE", file=sys.stderr)
        return 2
    with open(argv[0]) as f:
        values = parse(f.read().rstrip("\n"))
    print(f"total: {total(values):g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
EOF

cat > tests/unit/test_core.py <<'EOF'
import unittest

from tally.core import parse, total


class TestCore(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse("1\n2.5"), [1.0, 2.5])

    def test_total(self):
        self.assertEqual(total([1.0, 2.5]), 3.5)


if __name__ == "__main__":
    unittest.main()
EOF

cat > README.md <<'EOF'
# tally

Sums the numbers in a text file, one per line: `python3 -m tally numbers.txt` prints `total: 6`.
Tests: `python3 -m unittest discover -s tests/unit -t .`
EOF

python3 "$sdd" init \
  'acceptance_cmd=python3 -m unittest {files}' \
  'unit_cmd=python3 -m unittest discover -s tests/unit -t .' >/dev/null

git add -A
git commit -qm "chore: tally with sdd"
git push -q -u origin main
