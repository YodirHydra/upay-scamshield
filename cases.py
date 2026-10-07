"""
cases.py — simple case management for fraud analysts, with an audit trail and a PDF case report.

Cases live in the Streamlit session (one analyst session). In production they would be stored in upay's
case management database. Every action is written to the audit trail with a UTC timestamp.
"""
import io
from datetime import datetime, timezone

STATUSES = ["Open", "In progress", "Disputed by customer", "Resolved: confirmed fraud", "Resolved: false alarm",
            "Released: customer verified"]
# Analyst outcomes become training labels (feedback loop): 1 = confirmed fraud, 0 = genuine.
LABEL_OF = {"Resolved: confirmed fraud": 1, "Resolved: false alarm": 0, "Released: customer verified": 0}
# Service levels shown to the customer and the analyst (policy, set by upay).
SLA = {"HOLD review": "30 minutes", "Customer dispute": "24 hours"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def find_case(cases, ref):
    return next((c for c in cases if c["ref"] == ref), None)


def create_case(cases, kind, ref, title, priority, evidence, analyst="Fraud analyst"):
    """Create a case unless one already exists for the same transaction or ring (no duplicates)."""
    existing = find_case(cases, ref)
    if existing:
        return existing, False
    case = dict(id=f"CASE-{len(cases) + 1:04d}", kind=kind, ref=ref, title=title, priority=priority,
                status="Open", analyst=analyst, created=now(), evidence=evidence, notes=[], audit=[])
    case["audit"].append(dict(time=case["created"], actor=analyst, action="Case created",
                              detail=f"Escalated from {kind.lower()} {ref}"))
    cases.append(case)
    return case, True


def update_status(case, status, actor):
    if status != case["status"]:
        case["audit"].append(dict(time=now(), actor=actor, action="Status changed",
                                  detail=f"{case['status']} -> {status}"))
        case["status"] = status


def assign(case, analyst, actor):
    if analyst and analyst != case["analyst"]:
        case["audit"].append(dict(time=now(), actor=actor, action="Assigned", detail=f"{case['analyst']} -> {analyst}"))
        case["analyst"] = analyst


def add_note(case, text, actor):
    if text.strip():
        case["notes"].append(dict(time=now(), actor=actor, text=text.strip()))
        case["audit"].append(dict(time=now(), actor=actor, action="Note added", detail=text.strip()[:80]))


def customer_dispute(case, text, customer="Customer"):
    """Appeal path: the customer says a HOLD is wrong. The case is re-opened as 'Disputed by customer' for a
    second analyst, who either releases the money ('Released: customer verified') or confirms fraud."""
    case["audit"].append(dict(time=now(), actor=customer, action="Customer dispute",
                              detail=(text or "Customer says this transfer is genuine")[:120]))
    case["notes"].append(dict(time=now(), actor=customer, text=text or "Customer says this transfer is genuine."))
    if case["status"] != "Disputed by customer":
        case["audit"].append(dict(time=now(), actor="System", action="Status changed",
                                  detail=f"{case['status']} -> Disputed by customer"))
        case["status"] = "Disputed by customer"


def labels_from_cases(cases):
    """Resolved transaction cases as new labels: list of dicts txn_id, is_fraud, case, status."""
    out = []
    for c in cases:
        if c["kind"] == "Transaction" and c["status"] in LABEL_OF:
            ds, _, txn = c["ref"].rpartition(":")          # refs look like "B:T000123" (dataset:transaction)
            out.append(dict(dataset=ds or "?", txn_id=txn, is_fraud=LABEL_OF[c["status"]], case=c["id"], status=c["status"]))
    return out


def merge_labels(raw, labels):
    """Add analyst labels to a transaction log (an analyst decision overrides an older label). Returns (log, n_matched)."""
    import pandas as pd
    if not labels:
        return raw, 0
    lab = {str(x["txn_id"]): x["is_fraud"] for x in labels}
    out = raw.copy()
    if "is_fraud" not in out:
        out["is_fraud"] = pd.NA
    hit = out.txn_id.astype(str).isin(lab)
    out.loc[hit, "is_fraud"] = out.loc[hit, "txn_id"].astype(str).map(lab)
    return out, int(hit.sum())


def pseudonymise(value, salt="scamshield"):
    """One-way pseudonym for an ID in exports (same ID -> same pseudonym, the real ID cannot be read back)."""
    import hashlib
    return "ID-" + hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:10].upper()


def pdf_report(case):
    """Build a PDF case report (English) from the evidence captured when the case was created."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    NAVY, BLUE, LIGHT = colors.HexColor("#06306B"), colors.HexColor("#0B5CAD"), colors.HexColor("#EAF2FB")
    st = getSampleStyleSheet()
    st["Title"].textColor = NAVY
    st["Heading2"].textColor = BLUE
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=1.8 * cm, title=f"{case['id']} case report")

    def table(rows, widths, header=True):
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C7DA")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                 ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("LEFTPADDING", (0, 0), (-1, -1), 5)]
        if header:
            style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
        t.setStyle(TableStyle(style))
        return t

    import html as _h
    clean = lambda s: _h.escape(str(s)).replace("৳", "BDT ")   # escape user text; standard PDF fonts have no Taka sign
    P = lambda s: Paragraph(clean(s), st["BodyText"])
    ev = case["evidence"]
    story = [Paragraph(f"upay ScamShield: {case['id']}", st["Title"]),
             Paragraph(f"<b>{clean(case['title'])}</b>", st["BodyText"]),
             Spacer(1, 6),
             table([["Priority", case["priority"], "Status", case["status"]],
                    ["Analyst", case["analyst"], "Created", case["created"]],
                    ["Type", case["kind"], "Reference", case["ref"]]], [3 * cm, 5.5 * cm, 3 * cm, 5.5 * cm], header=False)]
    for heading, key in [("What happened", "what"), ("Why it is risky", "why"), ("What upay should do next", "next")]:
        if ev.get(key):
            story += [Paragraph(heading, st["Heading2"])]
            items = ev[key] if isinstance(ev[key], list) else [ev[key]]
            story += [P(("• " if len(items) > 1 else "") + str(x)) for x in items]
    if ev.get("engines"):
        story += [Paragraph("Engine agreement", st["Heading2"]),
                  table([["Engine", "Method", "Score", "Flag", "Finding"]] +
                        [[e["name"], e["method"], f"{e['score']:.1%}", "YES" if e["flagged"] else "no", P(e["note"])]
                         for e in ev["engines"]], [3.3 * cm, 3.4 * cm, 1.5 * cm, 1.2 * cm, 7.6 * cm])]
    if ev.get("profile"):
        story += [Paragraph("Customer behaviour vs. own baseline", st["Heading2"]),
                  table([["Dimension", "Customer baseline", "This transfer", "Finding"]] +
                        [[p["dimension"], P(p["baseline"]), P(p["this_transfer"]),
                          P(("UNUSUAL: " if p["unusual"] else "") + p["deviation"])] for p in ev["profile"]],
                        [3 * cm, 4.6 * cm, 3.6 * cm, 5.8 * cm])]
    if ev.get("ring_wallets"):
        story += [Paragraph("Wallets in this ring", st["Heading2"]), P(", ".join(ev["ring_wallets"]))]
    story += [Paragraph("Analyst notes", st["Heading2"])]
    story += [Paragraph(f"<b>{n['time']}</b> ({clean(n['actor'])}): {clean(n['text'])}", st["BodyText"])
              for n in case["notes"]] or [P("No notes yet.")]
    story += [Paragraph("Audit trail", st["Heading2"]),
              table([["Time (UTC)", "Actor", "Action", "Detail"]] +
                    [[a["time"], a["actor"], a["action"], P(a["detail"])] for a in case["audit"]],
                    [4 * cm, 3 * cm, 3 * cm, 7 * cm]),
              Spacer(1, 10),
              Paragraph("<i>Generated by upay ScamShield. AI findings are decision support; "
                        "final decisions are made by a human analyst.</i>", st["BodyText"])]
    doc.build(story)
    return buf.getvalue()
