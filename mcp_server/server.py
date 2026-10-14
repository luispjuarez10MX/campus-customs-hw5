"""Campus Customs MCP server.

The single gateway between the agents and data/campus_customs_new.db. Every
shop fact the agents see, and every change they make, goes through a tool here.

Read tools open the database read-only. Write tools enforce the shop rules in
code, so a confused agent cannot break them:

- dates come from desk.date_today, never the real clock
- vendor lead times come from vendors.lead_days
- a vendor with an unpaid invoice will not ship
- agents can only *request* payments; money moves only in approve_request,
  which is registered only in the human approver's server process
- no payment may take checking below zero, counting other pending requests
- customer messages are saved as drafts and never sent
"""

import calendar
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

DB_PATH = Path(
    os.environ.get(
        "CAMPUS_CUSTOMS_DB",
        Path(__file__).resolve().parents[1] / "data" / "campus_customs_new.db",
    )
)
CASH_ACCOUNT = "checking"
# The human-only approval tools exist only in a server process started with
# this flag. The backend sets it solely for its human-approval client; the
# agents' server process and Claude Code's .mcp.json server never have them.
HUMAN_APPROVER = os.environ.get("CAMPUS_CUSTOMS_HUMAN_APPROVER") == "1"
TICKET_STATUSES = ("open", "in_progress", "waiting_on_approval", "blocked", "resolved")

mcp = FastMCP("campus-customs")

# Workflow tables the original database does not have. They are created in the
# working copy only, so resetting from the original also clears them.
WORKFLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_requests (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER,                  -- invoice id or lease id
    vendor_id INTEGER,
    sku TEXT,
    size TEXT,
    qty INTEGER,
    amount REAL NOT NULL,
    ticket_id INTEGER,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    requested_on TEXT NOT NULL,      -- shop date
    status TEXT NOT NULL,            -- pending | approved | rejected
    decided_by TEXT,
    decided_on TEXT,
    decision_note TEXT,
    payment_id INTEGER,
    expected_arrival TEXT
);
CREATE TABLE IF NOT EXISTS customer_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    drafted_by TEXT NOT NULL,
    drafted_on TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft_not_sent'
);
"""


@contextmanager
def _connect(write: bool = False) -> Iterator[sqlite3.Connection]:
    """One connection per tool call: commit on success, roll back on error, always close."""
    if write:
        conn = sqlite3.connect(DB_PATH)
        conn.executescript(WORKFLOW_SCHEMA)
    else:
        # mode=ro: read tools can never write to the database.
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


def _has_table(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


def _balance(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT balance FROM cash_accounts WHERE name = ?", (CASH_ACCOUNT,)
    ).fetchone()
    return row["balance"]


def _pending_total(conn: sqlite3.Connection) -> float:
    if not _has_table(conn, "approval_requests"):
        return 0.0
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM approval_requests WHERE status = 'pending'"
    ).fetchone()
    return row["total"]


def _unpaid_invoices(conn: sqlite3.Connection, vendor_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, amount, due_date, status FROM invoices WHERE vendor_id = ? AND status != 'paid'",
        (vendor_id,),
    ).fetchall()


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _refuse(reason: str, **extra) -> dict:
    return {"ok": False, "refused": reason, **extra}


# ---------------------------------------------------------------- read tools


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved yet, with the shop's current date.

    Use this to see the work board: who asked, what for, and which SKU, lease,
    or invoice each ticket points to.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY id"
        ).fetchall()
        return {"today": _today(conn).isoformat(), "tickets": [dict(r) for r in rows]}


@mcp.tool
def list_tickets() -> dict:
    """List all tickets, open or resolved, with each one's status. For the dashboard."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
        return {
            "today": _today(conn).isoformat(),
            "tickets": [{**dict(r), "is_resolved": r["status"] == "resolved"} for r in rows],
        }


@mcp.tool
def list_approval_requests(status: Literal["pending", "approved", "rejected"] | None = None) -> dict:
    """List payment and purchase-order approval requests, optionally by status."""
    with _connect() as conn:
        if not _has_table(conn, "approval_requests"):
            return {"requests": []}
        sql, args = "SELECT * FROM approval_requests", ()
        if status:
            sql, args = sql + " WHERE status = ?", (status,)
        rows = conn.execute(sql + " ORDER BY id", args).fetchall()
        return {"requests": [dict(r) for r in rows]}


@mcp.tool
def get_vendor_invoice_status(invoice_id: int) -> dict:
    """Look up a vendor invoice and whether it blocks that vendor from shipping.

    Returns the invoice, its vendor and lead time, days overdue as of
    desk.date_today, and the earliest restock arrival if the invoice were
    paid today. A vendor with an unpaid invoice will not ship.
    """
    with _connect() as conn:
        today = _today(conn)
        row = conn.execute(
            """
            SELECT i.id, i.amount, i.due_date, i.status, i.description,
                   v.id AS vendor_id, v.name AS vendor_name, v.specialty, v.lead_days
            FROM invoices i JOIN vendors v ON v.id = i.vendor_id
            WHERE i.id = ?
            """,
            (invoice_id,),
        ).fetchone()
        if row is None:
            return {"error": f"Invoice {invoice_id} not found."}

        unpaid = row["status"] != "paid"
        days_overdue = (today - date.fromisoformat(row["due_date"])).days
        return {
            "today": today.isoformat(),
            "invoice_id": row["id"],
            "amount": row["amount"],
            "due_date": row["due_date"],
            "status": row["status"],
            "description": row["description"],
            "days_overdue": max(days_overdue, 0),
            "vendor": {
                "id": row["vendor_id"],
                "name": row["vendor_name"],
                "specialty": row["specialty"],
                "lead_days": row["lead_days"],
            },
            "vendor_will_ship": not unpaid,
            "earliest_arrival_if_paid_today": (
                today + timedelta(days=row["lead_days"])
            ).isoformat(),
        }


@mcp.tool
def get_lease_rent_due(lease_id: int) -> dict:
    """Look up rent owed on a lease and whether checking can cover it.

    Returns the lease, days until rent is due as of desk.date_today, the
    current checking balance, and the balance that would remain after paying.
    """
    with _connect() as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT * FROM leases WHERE id = ?", (lease_id,)
        ).fetchone()
        if lease is None:
            return {"error": f"Lease {lease_id} not found."}
        cash = conn.execute(
            "SELECT name, balance FROM cash_accounts WHERE name = 'checking'"
        ).fetchone()

        balance_after = cash["balance"] - lease["monthly_rent"]
        return {
            "today": today.isoformat(),
            "lease_id": lease["id"],
            "space_name": lease["space_name"],
            "landlord": lease["landlord"],
            "monthly_rent": lease["monthly_rent"],
            "next_due": lease["next_due"],
            "days_until_due": (date.fromisoformat(lease["next_due"]) - today).days,
            "notes": lease["notes"],
            "checking_balance": cash["balance"],
            "balance_after_payment": balance_after,
            "can_cover_rent": balance_after >= 0,
        }


@mcp.tool
def get_stock_and_pricing(sku: str, size: str, qty: int) -> dict:
    """Check stock for a SKU and size against a requested quantity, with pricing.

    Returns units on hand, the shortfall, unit cost and list price, and the
    margin. The margin % at list is also the largest discount before selling
    at a loss.
    """
    with _connect() as conn:
        item = conn.execute(
            "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if item is None:
            return {"error": f"No inventory row for {sku} size {size}."}
        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()

        result = {
            "sku": item["sku"],
            "name": item["name"],
            "size": item["size"],
            "location": item["location"],
            "requested_qty": qty,
            "on_hand": item["qty"],
            "shortfall": max(qty - item["qty"], 0),
        }
        if price is None:
            result["pricing"] = None
            return result

        unit_cost, list_price = price["unit_cost"], price["list_price"]
        result["pricing"] = {
            "unit_cost": unit_cost,
            "list_price": list_price,
            "unit_margin_at_list": list_price - unit_cost,
            "margin_pct_at_list": round((list_price - unit_cost) / list_price * 100, 1),
            "order_value_at_list": list_price * qty,
            "order_cost": unit_cost * qty,
        }
        return result


@mcp.tool
def list_restock_vendors() -> dict:
    """List every vendor with its specialty, lead time, and whether it will ship.

    A vendor will not ship while it has an unpaid invoice. Arrival dates use
    desk.date_today + vendors.lead_days. Pick the vendor whose specialty fits
    the product.
    """
    with _connect() as conn:
        today = _today(conn)
        vendors = []
        for v in conn.execute("SELECT * FROM vendors ORDER BY id").fetchall():
            unpaid = _unpaid_invoices(conn, v["id"])
            vendors.append({
                "vendor_id": v["id"],
                "name": v["name"],
                "specialty": v["specialty"],
                "lead_days": v["lead_days"],
                "unpaid_invoices": [dict(i) for i in unpaid],
                "will_ship": not unpaid,
                "earliest_arrival_if_ordered_today": (
                    today + timedelta(days=v["lead_days"])
                ).isoformat(),
            })
        return {"today": today.isoformat(), "vendors": vendors}


@mcp.tool
def get_cash_position() -> dict:
    """Summarize cash against everything the shop owes.

    Returns the checking balance, unpaid vendor invoices, upcoming rent,
    pending approval requests, and the cash left if every pending request
    were approved. No revenue comes in, so this balance is all the shop has.
    """
    with _connect() as conn:
        today = _today(conn)
        balance = _balance(conn)
        invoices = [
            {**dict(r), "days_overdue": max((today - date.fromisoformat(r["due_date"])).days, 0)}
            for r in conn.execute(
                """
                SELECT i.id AS invoice_id, v.name AS vendor, i.amount, i.due_date, i.status
                FROM invoices i JOIN vendors v ON v.id = i.vendor_id
                WHERE i.status != 'paid' ORDER BY i.due_date
                """
            ).fetchall()
        ]
        rent = [
            {**dict(r), "days_until_due": (date.fromisoformat(r["next_due"]) - today).days}
            for r in conn.execute(
                "SELECT id AS lease_id, landlord, monthly_rent, next_due FROM leases ORDER BY next_due"
            ).fetchall()
        ]
        pending = []
        if _has_table(conn, "approval_requests"):
            pending = [dict(r) for r in conn.execute(
                "SELECT id, kind, ref_id, amount, ticket_id, requested_by FROM approval_requests WHERE status = 'pending'"
            ).fetchall()]
        pending_total = sum(p["amount"] for p in pending)
        owed = sum(i["amount"] for i in invoices) + sum(r["monthly_rent"] for r in rent)
        return {
            "today": today.isoformat(),
            "checking_balance": balance,
            "unpaid_invoices": invoices,
            "upcoming_rent": rent,
            "pending_requests": pending,
            "pending_total": pending_total,
            "available_after_pending": balance - pending_total,
            "invoices_plus_rent_total": owed,
            "left_if_all_invoices_and_rent_paid": balance - owed,
        }


# --------------------------------------------------------------- agent writes


@mcp.tool
def request_payment(
    kind: Literal["invoice", "rent"],
    ref_id: int,
    reason: str,
    ticket_id: int | None = None,
    requested_by: str = "unknown",
) -> dict:
    """Ask the human approver to pay a vendor invoice or a lease's rent.

    kind="invoice" with ref_id = invoices.id, or kind="rent" with ref_id = leases.id.
    The amount always comes from the database. Nothing is paid until a human
    approves. Refused if it would push checking below zero after the other
    pending requests, if the bill is already paid, or if it is already pending.
    """
    with _connect(write=True) as conn:
        today = _today(conn)
        if kind == "invoice":
            bill = conn.execute("SELECT amount, status, vendor_id FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if bill is None:
                return _refuse(f"Invoice {ref_id} not found.")
            if bill["status"] == "paid":
                return _refuse(f"Invoice {ref_id} is already paid.")
            amount, vendor_id = bill["amount"], bill["vendor_id"]
        else:
            lease = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return _refuse(f"Lease {ref_id} not found.")
            amount, vendor_id = lease["monthly_rent"], None

        dup = conn.execute(
            "SELECT id FROM approval_requests WHERE kind = ? AND ref_id = ? AND status = 'pending'",
            (kind, ref_id),
        ).fetchone()
        if dup:
            return _refuse(f"A pending request already exists for this {kind}.", request_id=dup["id"])

        available = _balance(conn) - _pending_total(conn)
        if available - amount < 0:
            return _refuse(
                "Cash would go negative once pending requests are counted.",
                amount=amount, available_after_pending=available,
            )

        cur = conn.execute(
            """
            INSERT INTO approval_requests
                (kind, ref_id, vendor_id, amount, ticket_id, reason, requested_by, requested_on, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (kind, ref_id, vendor_id, amount, ticket_id, reason, requested_by, today.isoformat()),
        )
        return {
            "ok": True,
            "request_id": cur.lastrowid,
            "status": "pending",
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount,
            "available_after_pending": available - amount,
            "note": "Waiting for human approval. No money has moved.",
        }


@mcp.tool
def request_purchase_order(
    vendor_id: int,
    sku: str,
    size: str,
    qty: int,
    reason: str,
    ticket_id: int | None = None,
    requested_by: str = "unknown",
) -> dict:
    """Ask the human approver to buy restock from a vendor at pricing.unit_cost.

    Refused if the vendor has an unpaid invoice with no pending payment request
    (they won't ship), or if the cost would push checking below zero after the
    other pending requests. If the vendor's invoice payment is still pending,
    the PO can only be approved after that invoice is paid.
    """
    if qty <= 0:
        return _refuse("Quantity must be positive.")
    with _connect(write=True) as conn:
        today = _today(conn)
        vendor = conn.execute("SELECT name, lead_days FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return _refuse(f"Vendor {vendor_id} not found.")
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return _refuse(f"No pricing for {sku}.")
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return _refuse(f"{sku} has no size {size}.")

        blocking = []
        for inv in _unpaid_invoices(conn, vendor_id):
            pending = conn.execute(
                "SELECT id FROM approval_requests WHERE kind = 'invoice' AND ref_id = ? AND status = 'pending'",
                (inv["id"],),
            ).fetchone()
            if pending is None:
                return _refuse(
                    f"{vendor['name']} has unpaid invoice {inv['id']} and will not ship. "
                    "Request payment of that invoice first.",
                    invoice_id=inv["id"],
                )
            blocking.append(inv["id"])

        amount = round(price["unit_cost"] * qty, 2)
        available = _balance(conn) - _pending_total(conn)
        if available - amount < 0:
            return _refuse(
                "Cash would go negative once pending requests are counted.",
                amount=amount, available_after_pending=available,
            )

        cur = conn.execute(
            """
            INSERT INTO approval_requests
                (kind, vendor_id, sku, size, qty, amount, ticket_id, reason, requested_by, requested_on, status)
            VALUES ('purchase_order', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (vendor_id, sku, size, qty, amount, ticket_id, reason, requested_by, today.isoformat()),
        )
        return {
            "ok": True,
            "request_id": cur.lastrowid,
            "status": "pending",
            "vendor": vendor["name"],
            "amount": amount,
            "lead_days": vendor["lead_days"],
            "arrival_if_approved_today": (today + timedelta(days=vendor["lead_days"])).isoformat(),
            "waits_on_invoice_payment": blocking,
            "available_after_pending": available - amount,
            "note": "Waiting for human approval. Nothing has been ordered.",
        }


@mcp.tool
def draft_customer_message(
    ticket_id: int,
    subject: str,
    body: str,
    drafted_by: str = "unknown",
) -> dict:
    """Save a customer message as a draft for a human to review. It is NEVER sent.

    The recipient is always the ticket's requester.
    """
    with _connect(write=True) as conn:
        ticket = conn.execute("SELECT requester FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return _refuse(f"Ticket {ticket_id} not found.")
        cur = conn.execute(
            """
            INSERT INTO customer_drafts (ticket_id, recipient, subject, body, drafted_by, drafted_on)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, ticket["requester"], subject, body, drafted_by, _today(conn).isoformat()),
        )
        return {
            "ok": True,
            "draft_id": cur.lastrowid,
            "recipient": ticket["requester"],
            "status": "draft_not_sent",
        }


@mcp.tool
def update_ticket(
    ticket_id: int,
    status: Literal["open", "in_progress", "waiting_on_approval", "blocked", "resolved"],
    note: str,
    updated_by: str = "unknown",
) -> dict:
    """Set a ticket's status and append a dated note explaining the decision."""
    with _connect(write=True) as conn:
        ticket = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return _refuse(f"Ticket {ticket_id} not found.")
        entry = f"[{_today(conn).isoformat()} {updated_by}] {note}"
        notes = f"{ticket['notes']}\n{entry}" if ticket["notes"] else entry
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
        return {"ok": True, "ticket_id": ticket_id, "status": status, "note_added": entry}


# ---------------------------------------------------------- human-only writes
# Registered only when CAMPUS_CUSTOMS_HUMAN_APPROVER=1 (see bottom of file).
# This is the only code that moves money.


def _close_if_all_approved(conn: sqlite3.Connection, ticket_id: int | None, approver: str, today: date) -> int | None:
    """Mark the ticket resolved once its last pending request is approved.

    Only when the Boss left it `waiting_on_approval`, i.e. approval was the only
    thing it was waiting for. A ticket left `in_progress` (e.g. waiting on a
    customer reply) keeps its status.
    """
    if ticket_id is None:
        return None
    still_pending = conn.execute(
        "SELECT 1 FROM approval_requests WHERE ticket_id = ? AND status = 'pending'", (ticket_id,)
    ).fetchone()
    ticket = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if still_pending or ticket is None or ticket["status"] != "waiting_on_approval":
        return None
    entry = f"[{today.isoformat()} human] All approvals granted by {approver}."
    notes = f"{ticket['notes']}\n{entry}" if ticket["notes"] else entry
    conn.execute("UPDATE tickets SET status = 'resolved', notes = ? WHERE id = ?", (notes, ticket_id))
    return ticket_id


def approve_request(request_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Approve a pending request and move the money.

    Re-checks every rule at approval time, then in one transaction: writes the
    payment, debits checking, and marks the invoice paid, advances the lease's
    next_due by one month, or records the PO's expected arrival. If this was the
    ticket's last pending request and the ticket was waiting_on_approval, the
    ticket is marked resolved with a note naming the approver.
    """
    with _connect(write=True) as conn:
        today = _today(conn)
        req = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return _refuse(f"Request {request_id} not found.")
        if req["status"] != "pending":
            return _refuse(f"Request {request_id} is already {req['status']}.")

        balance = _balance(conn)
        if balance - req["amount"] < 0:
            return _refuse("Cash would go negative.", amount=req["amount"], checking_balance=balance)

        expected_arrival = None
        if req["kind"] == "invoice":
            inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
            if inv["status"] == "paid":
                return _refuse(f"Invoice {req['ref_id']} is already paid.")
        elif req["kind"] == "purchase_order":
            unpaid = _unpaid_invoices(conn, req["vendor_id"])
            if unpaid:
                return _refuse(
                    "Vendor still has an unpaid invoice and will not ship. Approve that invoice first.",
                    invoice_ids=[i["id"] for i in unpaid],
                )
            lead = conn.execute("SELECT lead_days FROM vendors WHERE id = ?", (req["vendor_id"],)).fetchone()
            expected_arrival = (today + timedelta(days=lead["lead_days"])).isoformat()

        payment = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (req["kind"], req["ref_id"] if req["kind"] != "purchase_order" else request_id,
             req["amount"], CASH_ACCOUNT, today.isoformat(), approved_by),
        )
        conn.execute(
            "UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
            (req["amount"], today.isoformat(), CASH_ACCOUNT),
        )
        if req["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
        elif req["kind"] == "rent":
            lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
            conn.execute(
                "UPDATE leases SET next_due = ? WHERE id = ?",
                (_add_month(date.fromisoformat(lease["next_due"])).isoformat(), req["ref_id"]),
            )
        conn.execute(
            """
            UPDATE approval_requests
            SET status = 'approved', decided_by = ?, decided_on = ?, payment_id = ?, expected_arrival = ?
            WHERE id = ?
            """,
            (approved_by, today.isoformat(), payment.lastrowid, expected_arrival, request_id),
        )
        return {
            "ok": True,
            "request_id": request_id,
            "payment_id": payment.lastrowid,
            "amount": req["amount"],
            "checking_balance": _balance(conn),
            "expected_arrival": expected_arrival,
            "ticket_resolved": _close_if_all_approved(conn, req["ticket_id"], approved_by, today),
        }


def reject_request(request_id: int, rejected_by: str, note: str = "") -> dict:
    """HUMAN ONLY. Reject a pending request. No money moves."""
    with _connect(write=True) as conn:
        req = conn.execute("SELECT status FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return _refuse(f"Request {request_id} not found.")
        if req["status"] != "pending":
            return _refuse(f"Request {request_id} is already {req['status']}.")
        conn.execute(
            """
            UPDATE approval_requests
            SET status = 'rejected', decided_by = ?, decided_on = ?, decision_note = ?
            WHERE id = ?
            """,
            (rejected_by, _today(conn).isoformat(), note, request_id),
        )
        return {"ok": True, "request_id": request_id, "status": "rejected"}


if HUMAN_APPROVER:
    mcp.tool(approve_request, tags={"human_only"})
    mcp.tool(reject_request, tags={"human_only"})


if __name__ == "__main__":
    mcp.run()
