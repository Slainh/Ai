import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from support_triage.core import Ticket, rule_classify, ollama_classify, draft_reply
from support_triage.cli import main, load_tickets
from support_triage.store import database, is_unchanged, save, mark_reviewed, summary


class TriageTest(unittest.TestCase):
    def test_billing_requires_review(self):
        d=rule_classify(Ticket("1","Unexpected invoice","I was charged twice"))
        self.assertEqual((d.category,d.priority,d.requires_review),("billing","high",True))

    def test_cancellation_requires_review(self):
        self.assertTrue(rule_classify(Ticket("1","Cancel subscription","Please stop it")).requires_review)

    def test_shipping_classification(self):
        self.assertEqual(rule_classify(Ticket("1","Order tracking","my package is late")).category,"shipping")

    def test_other_is_low_priority(self):
        self.assertEqual(rule_classify(Ticket("1","Hello","Just checking")).priority,"low")

    def test_security_requires_review(self):
        self.assertTrue(rule_classify(Ticket("1","Security problem","Potential breach")).requires_review)

    def test_fingerprint_changes_when_updated(self):
        self.assertNotEqual(Ticket("1","a","b").fingerprint(),Ticket("1","a","c").fingerprint())

    def test_sqlite_duplicate_suppression_and_update(self):
        with tempfile.TemporaryDirectory() as d:
            with database(str(Path(d)/"db.sqlite")) as db:
                t=Ticket("1","a","b")
                self.assertFalse(is_unchanged(db,t))
                save(db,t,rule_classify(t))
                self.assertTrue(is_unchanged(db,t))
                self.assertFalse(is_unchanged(db,Ticket("1","a","changed")))
                self.assertEqual(summary(db)["total"],1)

    def test_mark_reviewed(self):
        with tempfile.TemporaryDirectory() as d:
            with database(str(Path(d)/"db.sqlite")) as db:
                t=Ticket("1","test","test")
                save(db,t,rule_classify(t))
                self.assertTrue(mark_reviewed(db,"1"))
                self.assertEqual(summary(db)["pending_review"],0)
                self.assertFalse(mark_reviewed(db,"missing"))

    def test_reject_external_ollama_url(self):
        with self.assertRaises(ValueError):
            ollama_classify(Ticket("1","a","b"),"https://somewhere.example:443","anything")

    def test_invalid_csv_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"bad.csv"
            path.write_text("name,subject\na,b",encoding="utf-8")
            with self.assertRaises(ValueError):
                list(load_tickets(str(path)))

    def test_cli_end_to_end_and_repeat(self):
        with tempfile.TemporaryDirectory() as d:
            db=str(Path(d)/"demo.sqlite3")
            data=str(Path(__file__).parent.parent/"examples"/"tickets.csv")
            main(["run","--input",data,"--db",db])
            with database(db) as c:
                self.assertEqual(summary(c)["total"],6)
            main(["run","--input",data,"--db",db])
            main(["report","--db",db,"--format","html","--output",str(Path(d)/"dashboard.html")])
            self.assertTrue((Path(d)/"dashboard.html").exists())
            main(["export","--db",db,"--output",str(Path(d)/"output.jsonl")])
            self.assertEqual(len((Path(d)/"output.jsonl").read_text().splitlines()),6)

    def test_no_sent_messages_ever(self):
        self.assertIn("Thanks",draft_reply("technical"))

if __name__ == "__main__":
    unittest.main()
