#!/bin/sh
# Agent Company: a live demo on this computer. Builds a small demo repository, seals one evidence record,
# and opens the Guild on it in your browser. Nothing outside ~/agent-company-demo is changed. Ctrl+C stops it.
set -e
AC="$(cd "$(dirname "$0")/.." && pwd)/agent_company.py"
DEMO="$HOME/agent-company-demo"
if [ ! -d "$DEMO/.git" ]; then
  rm -rf "$DEMO/docs" "$DEMO/.claude" "$DEMO/AGENTS.md"
  mkdir -p "$DEMO/tests" && cd "$DEMO"
  command -v git >/dev/null || { echo "git isn't installed: run  xcode-select --install  then try again"; exit 1; }
  git init -q .
  git symbolic-ref HEAD refs/heads/main
  git config user.email demo@example.test
  git config user.name "Demo"
  cat > ratelimit.py <<'PY'
def allow(counts, client, limit=5):
    """Allow a request if the client is under its limit; never drop silently."""
    counts[client] = counts.get(client, 0) + 1
    return counts[client] <= limit
PY
  cat > tests/test_ratelimit.py <<'PY'
import unittest
from ratelimit import allow

class RateLimit(unittest.TestCase):
    def test_fair_share(self):
        c = {}
        self.assertTrue(all(allow(c, "a") for _ in range(5)))
        self.assertFalse(allow(c, "a"))
        self.assertTrue(allow(c, "b"))

if __name__ == "__main__":
    unittest.main()
PY
  git add -A
  git commit -qm "Rate limiter with tests"
  git checkout -qb feat/rate-limit
  python3 "$AC" init . >/dev/null
fi
cd "$DEMO"
echo "== Sealing quest 001: re-running the tests, then writing a signed, chained evidence record"
python3 "$AC" seal . --quest 001 --pr https://github.com/acme/shop/pull/12 --verdict approve --evaluator "Sera Truecheck" --builder "Brannoc Forgehand" --test-cmd "python3 -m unittest -q tests.test_ratelimit" || true
echo
echo "== Verifying every record in the ledger"
python3 "$AC" verify . || true
echo
echo "== Harness in this repo (install it from the Forge, or: python3 $AC harness $DEMO)"
python3 "$AC" harness . --check || true
echo
echo "== Opening the Guild on $DEMO"
echo "   Claude opens it in the Claude app's browser; you can also open the address below in any browser."
HERE_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 -u "$AC" guild . --no-browser --port 8765 | tee "$HERE_DIR/last-url.txt"
