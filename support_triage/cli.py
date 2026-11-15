"""Zero-dependency CLI: demo, stats, export and human review."""
from __future__ import annotations
import argparse
import csv
import html
import json
import sys
from pathlib import Path
from .core import Ticket, ollama_classify, rule_classify
from .store import database, is_unchanged, mark_reviewed, save, summary


def load_tickets(path: str):
    with open(path, encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {"ticket_id","subject","message"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError("CSV requires ticket_id, subject, message columns")
        for row in reader:
            tid = (row["ticket_id"] or "").strip()
            if not tid or len(tid)>100:
                raise ValueError("Each row needs a valid ticket_id (1..100 characters)")
            yield Ticket(tid, (row["subject"] or "")[:500], (row["message"] or "")[:3000])


def run(args):
    processed = unchanged = fallback = 0
    with database(args.db) as conn:
        for ticket in load_tickets(args.input):
            if is_unchanged(conn,ticket):
                unchanged += 1
                continue
            if args.engine == "ollama":
                try:
                    decision=ollama_classify(ticket,args.ollama_url,args.model,timeout=args.timeout)
                except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
                    print(f"Ticket {ticket.ticket_id}: Ollama unavailable/invalid; using rules ({type(exc).__name__})",file=sys.stderr)
                    decision=rule_classify(ticket)
                    fallback += 1
            else:
                decision=rule_classify(ticket)
            save(conn,ticket,decision)
            processed += 1
        print(json.dumps({"processed":processed,"unchanged_skipped":unchanged,"ollama_fallbacks":fallback,**summary(conn)},indent=2))


def report(args):
    with database(args.db) as conn:
        data=summary(conn)
        if args.format == "html":
            rows="".join(f"<tr><td>{html.escape(cat)}</td><td>{count}</td></tr>" for cat,count in sorted(data['by_category'].items()))
            content=f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Support Operations Demo</title>
<style>body{{font:16px system-ui;margin:3rem auto;max-width:680px;padding:0 1rem;color:#17212d}}h1{{font-size:2rem}}.stats{{display:flex;gap:1rem;flex-wrap:wrap}}.stat{{padding:1.4rem;border:1px solid #ddd;border-radius:12px;flex:1}}.number{{font-size:2rem;font-weight:700}}table{{width:100%;border-collapse:collapse;margin-top:2rem}}td,th{{text-align:left;padding:.7rem;border-bottom:1px solid #ddd}}footer{{color:#555;margin-top:3rem}}</style>
<h1>AI Support Operations – Demo</h1><p>Local, synthetic-data portfolio demonstration.</p><div class="stats"><div class="stat"><div class="number">{data['total']}</div>Tickets</div><div class="stat"><div class="number">{data['pending_review']}</div>Pending review</div></div><table><thead><tr><th>Category</th><th>Tickets</th></tr></thead><tbody>{rows}</tbody></table><footer>No live customer data. No messages are sent automatically.</footer></html>"""
            Path(args.output).parent.mkdir(parents=True,exist_ok=True)
            Path(args.output).write_text(content,encoding="utf-8")
            print(f"Dashboard written to {args.output}")
        else:
            print(json.dumps(data,indent=2))


def export(args):
    with database(args.db) as conn:
        rows=conn.execute("SELECT ticket_id,category,priority,summary,requires_review,reply_draft,engine,reviewed FROM tickets ORDER BY ticket_id").fetchall()
        keys=["ticket_id","category","priority","summary","requires_review","reply_draft","engine","reviewed"]
        Path(args.output).parent.mkdir(parents=True,exist_ok=True)
        with open(args.output,"w",encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(dict(zip(keys,row)),ensure_ascii=False)+"\n")
        print(f"Exported {len(rows)} decisions to {args.output}; NO messages sent")


def review(args):
    with database(args.db) as conn:
        ok=mark_reviewed(conn,args.ticket_id)
        print("Reviewed" if ok else "Ticket not found")
        if not ok:
            sys.exit(1)


def main(argv=None):
    parser=argparse.ArgumentParser(description="Local AI-assisted support-ticket triage portfolio demo")
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("run")
    p.add_argument("--input",default="examples/tickets.csv")
    p.add_argument("--db",default="runs/demo.sqlite3")
    p.add_argument("--engine",choices=("rules","ollama"),default="rules")
    p.add_argument("--ollama-url",default="http://127.0.0.1:11434")
    p.add_argument("--model",default="gemma3:12b")
    p.add_argument("--timeout",type=float,default=30)
    p.set_defaults(func=run)
    p=sub.add_parser("report")
    p.add_argument("--db",default="runs/demo.sqlite3")
    p.add_argument("--format",choices=("json","html"),default="json")
    p.add_argument("--output",default="runs/dashboard.html")
    p.set_defaults(func=report)
    p=sub.add_parser("export")
    p.add_argument("--db",default="runs/demo.sqlite3")
    p.add_argument("--output",default="runs/decisions.jsonl")
    p.set_defaults(func=export)
    p=sub.add_parser("review")
    p.add_argument("ticket_id")
    p.add_argument("--db",default="runs/demo.sqlite3")
    p.set_defaults(func=review)
    args=parser.parse_args(argv)
    args.func(args)

if __name__ == "__main__":
    main()
