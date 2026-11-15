# Test report

Tested: 2026-11-15, Python 3.13 (standard library only).

## Automated tests

Command:

```bash
python3 -m unittest discover -s tests -v
```

Result: **12 tests passed**.

Covered: sensitive-topic handling; billing/cancellation/shipping/security classification; stable ticket fingerprints; SQLite duplicate suppression and updates; review status; localhost-only Ollama URL guard; CSV validation; full CLI import/report/export flow.

## Demonstration

```bash
python3 -m support_triage.cli run --input examples/tickets.csv --db runs/demo.sqlite3
python3 -m support_triage.cli run --input examples/tickets.csv --db runs/demo.sqlite3
python3 -m support_triage.cli report --db runs/demo.sqlite3 --format html --output runs/dashboard.html
python3 -m support_triage.cli export --db runs/demo.sqlite3 --output runs/decisions.jsonl
```

Observed:
- First run: processed 6 tickets; retained 6.
- Second run: processed 0; skipped 6 unchanged tickets.
- HTML dashboard and JSONL export generated successfully.
- No customer messages sent; sample CSV contains synthetic messages only.

## Not tested

- Live Ollama inference (no model/service available in the test container).
- Production helpdesk or e-commerce API integration.
- Production concurrency, load, authentication, personal data, and recovery scenarios.

This project is a portfolio **demonstrator**, not a production service.