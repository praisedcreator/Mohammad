"""Local SQLite proposal store and demo-only human review.

This is a teaching adapter. It does not authenticate people or connect to an ERP.
The MCP server exposes proposal creation and reads; review is a separate CLI.
"""
from __future__ import annotations

import copy
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from business import Rejected, canonical, digest, evaluate, fingerprint

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def now():
    return datetime.now(timezone.utc).isoformat()


class InventoryStore:
    def __init__(self, db_path, fixture_path=None):
        self.path = Path(db_path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fixture_path = Path(fixture_path or ROOT / "fixtures.json")
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS proposals (
                    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL,
                    request_hash TEXT NOT NULL, payload TEXT NOT NULL,
                    payload_hash TEXT NOT NULL, status TEXT NOT NULL,
                    reviewer TEXT, reviewed_at TEXT, review_comment TEXT,
                    result TEXT
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL, call_id TEXT NOT NULL,
                    event TEXT NOT NULL, outcome TEXT NOT NULL,
                    proposal_id TEXT, details TEXT NOT NULL
                );
                PRAGMA user_version = 1;
            """)

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def evidence(self):
        fixture = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        inventory, policy = copy.deepcopy(fixture["inventory"]), copy.deepcopy(fixture["policy"])
        # The time means "fixture read at", not "live inventory updated at".
        inventory["as_of"] = policy["as_of"] = now()
        return fixture["case"], inventory, policy

    @staticmethod
    def _event(db, event, outcome, details, proposal_id=None, call_id=None):
        db.execute(
            "INSERT INTO events(timestamp,call_id,event,outcome,proposal_id,details) VALUES (?,?,?,?,?,?)",
            (now(), call_id or str(uuid.uuid4()), event, outcome, proposal_id, canonical(details)),
        )

    def event(self, event, outcome, details, proposal_id=None, call_id=None):
        with self.connection(write=True) as db:
            self._event(db, event, outcome, details, proposal_id, call_id)

    @staticmethod
    def _read(db, proposal_id):
        row = db.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
        if row is None:
            raise Rejected("Unknown proposal ID")
        payload = json.loads(row["payload"])
        if digest(payload) != row["payload_hash"]:
            raise Rejected("Stored proposal content does not match its hash")
        return row, payload

    @staticmethod
    def _public(row, payload):
        return {
            **payload, "proposal_hash": row["payload_hash"], "status": row["status"],
            "reviewer": row["reviewer"], "reviewed_at": row["reviewed_at"],
            "review_comment": row["review_comment"],
            "simulation_receipt": json.loads(row["result"]) if row["result"] else None,
            "execution_performed": False,
        }

    def get(self, proposal_id):
        with self.connection() as db:
            row, payload = self._read(db, proposal_id)
            return self._public(row, payload)

    def create(self, quantity, rationale, alternatives, request_id, call_id=None):
        if not isinstance(request_id, str) or not 1 <= len(request_id.strip()) <= 100:
            raise Rejected("request_id must contain 1 to 100 characters")
        if not isinstance(rationale, str) or not 1 <= len(rationale.strip()) <= 1500:
            raise Rejected("rationale must contain 1 to 1500 characters")
        if not isinstance(alternatives, list) or not 1 <= len(alternatives) <= 5 or any(
            not isinstance(item, str) or not 1 <= len(item.strip()) <= 600 for item in alternatives
        ):
            raise Rejected("Provide one to five nonempty alternatives, each at most 600 characters")
        # Check scalar types even on retries; bool and floating point quantities are refused.
        from business import number
        number(quantity, "quantity", minimum=1, integer=True)
        request_id, rationale = request_id.strip(), rationale.strip()
        alternatives = [item.strip() for item in alternatives]
        case, inventory, policy = self.evidence()
        request_hash = digest({"quantity": quantity, "rationale": rationale,
                               "alternatives": alternatives, "case": case})
        with self.connection(write=True) as db:
            existing = db.execute("SELECT id,request_hash FROM proposals WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise Rejected("request_id was already used for different proposal content; use a new ID")
                row, payload = self._read(db, existing["id"])
                self._event(db, "proposal_retry", "ok", {"request_id": request_id}, row["id"], call_id)
                return {**self._public(row, payload), "idempotent_retry": True}
            checks = evaluate(quantity, inventory, policy, case)
            if not checks["allowed"]:
                raise Rejected("Transfer fails policy: " + ", ".join(checks["violations"]))
            created = datetime.now(timezone.utc)
            payload = {
                "proposal_id": str(uuid.uuid4()), "request_id": request_id,
                "created_at": created.isoformat(),
                "expires_at": (created + timedelta(hours=1)).isoformat(),
                "source_version": VERSION, "data_mode": "demo_fixture",
                "case": case, "action": "PROPOSE_WAREHOUSE_TRANSFER", "quantity": quantity,
                "unit": inventory["unit"], "rationale": rationale, "alternatives": alternatives,
                "calculations": checks, "evidence": {"inventory": inventory, "policy": policy},
                "required_approval_group": "procurement", "execution_mode": "simulation_only",
            }
            proposal_hash = digest(payload)
            db.execute(
                "INSERT INTO proposals(id,request_id,request_hash,payload,payload_hash,status) VALUES (?,?,?,?,?,?)",
                (payload["proposal_id"], request_id, request_hash, canonical(payload), proposal_hash, "AWAITING_REVIEW"),
            )
            self._event(db, "proposal_created", "ok", {"proposal_hash": proposal_hash}, payload["proposal_id"], call_id)
            row, payload = self._read(db, payload["proposal_id"])
            return {**self._public(row, payload), "idempotent_retry": False}

    @staticmethod
    def _unexpired(payload):
        if datetime.now(timezone.utc) > datetime.fromisoformat(payload["expires_at"]):
            raise Rejected("Proposal expired; create a new proposal and request a new review")

    def review(self, proposal_id, expected_hash, decision, reviewer, comment):
        # This CLI identity is a demo label. Production identity must come from verified SSO.
        if decision not in {"approve", "reject"}:
            raise Rejected("decision must be approve or reject")
        if not reviewer.strip() or not comment.strip():
            raise Rejected("A demo reviewer label and review comment are required")
        with self.connection(write=True) as db:
            row, payload = self._read(db, proposal_id)
            if expected_hash != row["payload_hash"]:
                raise Rejected("Review hash does not match the exact proposal")
            if row["status"] != "AWAITING_REVIEW":
                raise Rejected("Proposal has already been reviewed")
            if decision == "approve":
                self._unexpired(payload)
            status = "APPROVED" if decision == "approve" else "REJECTED"
            db.execute("UPDATE proposals SET status=?,reviewer=?,reviewed_at=?,review_comment=? WHERE id=?",
                       (status, reviewer.strip(), now(), comment.strip(), proposal_id))
            self._event(db, "human_review_demo", "ok", {"decision": decision, "reviewer": reviewer,
                        "comment": comment, "proposal_hash": expected_hash}, proposal_id)
            row, payload = self._read(db, proposal_id)
            return self._public(row, payload)

    def simulate(self, proposal_id):
        with self.connection(write=True) as db:
            row, payload = self._read(db, proposal_id)
            if row["status"] == "SIMULATED":
                return self._public(row, payload)
            if row["status"] != "APPROVED":
                raise Rejected("Simulation requires an approved proposal")
            self._unexpired(payload)
            case, inventory, policy = self.evidence()
            if case != payload["case"] or fingerprint(inventory, policy) != payload["calculations"]["evidence_fingerprint"]:
                raise Rejected("Inventory or policy changed; a new proposal and review are required")
            if not evaluate(payload["quantity"], inventory, policy, case)["allowed"]:
                raise Rejected("Current evidence does not pass transfer checks")
            receipt = {"receipt_id": "SIM-" + proposal_id, "simulated_at": now(),
                       "quantity": payload["quantity"], "real_stock_moved": False,
                       "note": "Local receipt only. No stock, external system or ERP document was changed."}
            db.execute("UPDATE proposals SET status='SIMULATED',result=? WHERE id=?", (canonical(receipt), proposal_id))
            self._event(db, "transfer_simulated", "ok", receipt, proposal_id)
            row, payload = self._read(db, proposal_id)
            return self._public(row, payload)

    def traces(self, proposal_id=None, limit=50):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise Rejected("limit must be an integer from 1 to 500")
        with self.connection() as db:
            if proposal_id:
                rows = db.execute("SELECT * FROM events WHERE proposal_id=? ORDER BY sequence DESC LIMIT ?",
                                  (proposal_id, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM events ORDER BY sequence DESC LIMIT ?", (limit,)).fetchall()
            return [{**dict(row), "details": json.loads(row["details"])} for row in reversed(rows)]
