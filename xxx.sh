# from repo root, with your backend venv active (scripts read .env automatically)

OK=/tmp/fundamentals_ok.txt
FAIL=/tmp/fundamentals_fail.txt
: > "$OK"; : > "$FAIL"

i=0
while IFS= read -r t; do
  [ -z "$t" ] && continue
  i=$((i+1))
  echo "[fundamentals] ($i) $t"
  PYTHONPATH=. python -m ops.run_backfill --ticker "$t" \
    && echo "$t" >> "$OK" \
    || echo "$t" >> "$FAIL"
  sleep 0.6   # be gentle to SEC; raise if you see throttling
done < /tmp/missing_fundamentals.txt
