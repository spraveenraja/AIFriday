from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import date, timedelta

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "assurance_demo.sqlite3"
AS_OF = date(2026, 11, 5)

# All entities and records below are synthetic demonstration fixtures.
ENGAGEMENTS = [
    ("ENG-001", "Northstar Platform Build", "Aster Delivery", "Software Engineering", "Green"),
    ("ENG-002", "Keystone Cloud Renewal", "Aster Delivery", "Modernization", "Green"),
    ("ENG-003", "Lumen Service Desk", "Aster Delivery", "IT Operations", "Green"),
    ("ENG-004", "Bluepeak Claims Portal", "Aster Delivery", "Software Engineering", "Amber"),
    ("ENG-005", "Silverline Data Move", "Aster Delivery", "Modernization", "Green"),
    ("ENG-006", "Cedar Payments Ops", "Aster Delivery", "IT Operations", "Green"),
    ("ENG-007", "Atlas Engineering", "Beacon Delivery", "Software Engineering", "Red"),
    ("ENG-008", "Juniper Mobile Refresh", "Beacon Delivery", "Modernization", "Green"),
    ("ENG-009", "Quartz Support Hub", "Beacon Delivery", "IT Operations", "Amber"),
    ("ENG-010", "Harbor Digital Forms", "Beacon Delivery", "Software Engineering", "Green"),
    ("ENG-011", "Willow Cloud Shift", "Beacon Delivery", "Modernization", "Amber"),
    ("SRV-012", "Meridian Service", "Beacon Delivery", "IT Operations", "Amber"),
    ("ENG-013", "Meridian API Studio", "Cinder Delivery", "Software Engineering", "Amber"),
    ("ENG-014", "Pioneer Core Upgrade", "Cinder Delivery", "Modernization", "Red"),
    ("ENG-015", "Copperfield App Support", "Cinder Delivery", "IT Operations", "Green"),
    ("ENG-016", "Orchid Commerce", "Cinder Delivery", "Software Engineering", "Green"),
    ("ENG-017", "Summit Data Platform", "Cinder Delivery", "Modernization", "Amber"),
    ("ENG-018", "Mosaic Cloud Ops", "Cinder Delivery", "IT Operations", "Green"),
    ("ENG-019", "Redwood Client Apps", "Dovetail Delivery", "Software Engineering", "Green"),
    ("ENG-020", "Cobalt Integration", "Dovetail Delivery", "Modernization", "Amber"),
    ("ENG-021", "Orion Operations", "Dovetail Delivery", "IT Operations", "Red"),
    ("ENG-022", "Maple Lending Suite", "Dovetail Delivery", "Software Engineering", "Green"),
    ("ENG-023", "Solstice Data Estate", "Dovetail Delivery", "Modernization", "Green"),
    ("ENG-024", "Willowbranch Service", "Dovetail Delivery", "IT Operations", "Green"),
    ("ENG-025", "Aurora Customer App", "Ember Delivery", "Software Engineering", "Amber"),
    ("ENG-026", "Summit Product Core", "Ember Delivery", "Modernization", "Red"),
    ("ENG-027", "Pebble Contact Center", "Ember Delivery", "IT Operations", "Amber"),
    ("ENG-028", "Fable Analytics", "Ember Delivery", "Software Engineering", "Green"),
]

UNITS = ["Aster Delivery", "Beacon Delivery", "Cinder Delivery", "Dovetail Delivery", "Ember Delivery"]


def _measures(engagement_id: str, status: str):
    # Values intentionally reconcile to the synthetic portfolio status mix.
    if engagement_id == "ENG-007":
        return dict(delivery=97.0, release_fail=25.0, slo=99.1, critical_release=0,
                    critical_slo=0, penalty=0.0, customer_impact=0, repeat=18.0,
                    overdue=20.0, trace=88.0, confidence="High",
                    reason="Verified production defect leakage and a 25% failed-release rate exceed the Red release-quality band.")
    if engagement_id == "SRV-012":
        return dict(delivery=98.0, release_fail=4.0, slo=99.0, critical_release=0,
                    critical_slo=0, penalty=0.0, customer_impact=0, repeat=8.0,
                    overdue=18.0, trace=64.0, confidence="Medium",
                    reason="Service outcomes are stable; sampled release traceability is 64%, a verified Amber evidence-control gap.")
    if status == "Green":
        return dict(delivery=96.5, release_fail=5.0, slo=98.5, critical_release=0,
                    critical_slo=0, penalty=0.0, customer_impact=0, repeat=7.0,
                    overdue=8.0, trace=97.0, confidence="High",
                    reason="Current evidence shows critical measures within the proposed Green bands.")
    if status == "Amber":
        return dict(delivery=91.0, release_fail=12.0, slo=94.4, critical_release=0,
                    critical_slo=0, penalty=0.0, customer_impact=1, repeat=18.0,
                    overdue=24.0, trace=79.0, confidence="Medium",
                    reason="A verified warning signal requires follow-up; no critical Red trigger is present.")
    red_map = {
        "ENG-014": dict(delivery=74.0, release_fail=23.0, slo=97.0, critical_release=0,
                        critical_slo=0, penalty=0.0, customer_impact=1, repeat=32.0,
                        overdue=46.0, trace=76.0, confidence="High",
                        reason="Delivery predictability is below 80% and repeat findings exceed 25%.") ,
        "ENG-021": dict(delivery=96.0, release_fail=8.0, slo=89.0, critical_release=0,
                        critical_slo=1, penalty=18000.0, customer_impact=1, repeat=10.0,
                        overdue=21.0, trace=82.0, confidence="High",
                        reason="A verified critical SLO breach and synthetic penalty exposure trigger Red service stability.") ,
        "ENG-026": dict(delivery=82.0, release_fail=22.0, slo=96.0, critical_release=1,
                        critical_slo=0, penalty=0.0, customer_impact=1, repeat=29.0,
                        overdue=48.0, trace=68.0, confidence="High",
                        reason="A verified severity 1 customer-impacting release incident triggers Red.") ,
    }
    return red_map.get(engagement_id, red_map["ENG-014"])


def _derived_status(m):
    # Transparent demo roll-up: any verified critical Red trigger dominates; otherwise
    # any Amber dimension makes the engagement Amber. Unknown evidence alone is not Red.
    red = (m["release_fail"] > 20 or m["delivery"] < 80 or m["repeat"] > 25 or
           m["overdue"] > 40 or m["trace"] < 60 or m["critical_release"] or
           m["critical_slo"] or m["penalty"] > 0 or m["customer_impact"] >= 2)
    if red: return "Red"
    amber = (m["delivery"] <= 95 or m["release_fail"] > 10 or m["slo"] <= 95 or
             m["repeat"] >= 10 or m["overdue"] > 15 or m["trace"] <= 95 or m["customer_impact"] == 1)
    return "Amber" if amber else "Green"


def _create_schema(conn):
    conn.executescript("""
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS engagements (
      engagement_id TEXT PRIMARY KEY, name TEXT NOT NULL, business_unit TEXT NOT NULL,
      engagement_type TEXT NOT NULL, overall_status TEXT NOT NULL,
      as_of TEXT NOT NULL, health_reason TEXT NOT NULL, evidence_confidence TEXT NOT NULL,
      synthetic INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS observations (
      observation_id INTEGER PRIMARY KEY AUTOINCREMENT, engagement_id TEXT NOT NULL,
      dimension TEXT NOT NULL, metric TEXT NOT NULL, value REAL, unit TEXT NOT NULL,
      status TEXT NOT NULL, period TEXT NOT NULL, evidence_date TEXT NOT NULL,
      confidence TEXT NOT NULL, explanation TEXT NOT NULL,
      FOREIGN KEY(engagement_id) REFERENCES engagements(engagement_id)
    );
    CREATE TABLE IF NOT EXISTS findings (
      finding_id TEXT PRIMARY KEY, engagement_id TEXT NOT NULL, category TEXT NOT NULL,
      severity TEXT NOT NULL, summary TEXT NOT NULL, repeat_flag INTEGER NOT NULL,
      customer_impact TEXT NOT NULL, finding_date TEXT NOT NULL, evidence_ref TEXT NOT NULL,
      synthetic INTEGER NOT NULL DEFAULT 1,
      FOREIGN KEY(engagement_id) REFERENCES engagements(engagement_id)
    );
    CREATE TABLE IF NOT EXISTS releases (
      release_id TEXT PRIMARY KEY, engagement_id TEXT NOT NULL, release_date TEXT NOT NULL,
      failed INTEGER NOT NULL, severity TEXT NOT NULL, approval_evidence INTEGER NOT NULL,
      test_evidence INTEGER NOT NULL, change_evidence INTEGER NOT NULL,
      fully_traceable INTEGER NOT NULL, evidence_ref TEXT NOT NULL,
      FOREIGN KEY(engagement_id) REFERENCES engagements(engagement_id)
    );
    CREATE TABLE IF NOT EXISTS actions (
      action_id TEXT PRIMARY KEY, engagement_id TEXT NOT NULL, trigger_ref TEXT NOT NULL,
      title TEXT NOT NULL, owner TEXT NOT NULL, contributors TEXT NOT NULL,
      horizon INTEGER NOT NULL, due_date TEXT NOT NULL, expected_outcome TEXT NOT NULL,
      success_measure TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL,
      completion_evidence TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
      synthetic INTEGER NOT NULL DEFAULT 1,
      FOREIGN KEY(engagement_id) REFERENCES engagements(engagement_id)
    );
    CREATE TABLE IF NOT EXISTS recommendations (
      recommendation_id TEXT PRIMARY KEY, engagement_id TEXT NOT NULL,
      trigger_ref TEXT NOT NULL, title TEXT NOT NULL, rationale TEXT NOT NULL,
      owner TEXT NOT NULL, horizon INTEGER NOT NULL, outcome TEXT NOT NULL,
      success_measure TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
      confidence TEXT NOT NULL DEFAULT 'Medium', model_name TEXT NOT NULL DEFAULT 'Seeded synthetic draft', assumptions TEXT NOT NULL DEFAULT '', synthetic INTEGER NOT NULL DEFAULT 1,
      FOREIGN KEY(engagement_id) REFERENCES engagements(engagement_id)
    );
    CREATE TABLE IF NOT EXISTS recommendation_events (
      event_id INTEGER PRIMARY KEY AUTOINCREMENT, recommendation_id TEXT NOT NULL,
      decision TEXT NOT NULL, reviewer TEXT NOT NULL, event_time TEXT NOT NULL,
      FOREIGN KEY(recommendation_id) REFERENCES recommendations(recommendation_id)
    );
    CREATE TABLE IF NOT EXISTS action_events (
      event_id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT NOT NULL,
      from_status TEXT NOT NULL, to_status TEXT NOT NULL, changed_by TEXT NOT NULL,
      event_time TEXT NOT NULL, FOREIGN KEY(action_id) REFERENCES actions(action_id)
    );
    """)


def _seed(conn):
    for eid, name, unit, kind, status in ENGAGEMENTS:
        m = _measures(eid, status)
        calculated_status = _derived_status(m)
        if calculated_status != status:
            raise ValueError(f"Synthetic health fixture for {eid} does not match its expected case status.")
        conn.execute("INSERT INTO engagements VALUES (?,?,?,?,?,?,?,?,1)",
                     (eid, name, unit, kind, calculated_status, AS_OF.isoformat(), m["reason"], m["confidence"]))
        obs = [
            ("Delivery Predictability", "Commitments met", m["delivery"], "%", "Higher is better"),
            ("Release Quality", "Failed / rolled-back releases", m["release_fail"], "%", "Lower is better"),
            ("Service Stability", "SLO compliance", m["slo"], "%", "Higher is better"),
            ("Service Stability", "SLO breach events", (1 if m["critical_slo"] or m["slo"] <= 95 else 0), "count", "Critical or threshold breach events"),
            ("Service Stability", "Penalty exposure", m["penalty"], "USD", "Synthetic assessed/exposure amount"),
            ("Customer Impact", "Material customer signals", m["customer_impact"], "count", "Verified signals"),
            ("Findings & Actions", "Repeat findings", m["repeat"], "%", "Lower is better"),
            ("Findings & Actions", "Overdue actions", m["overdue"], "%", "Lower is better"),
            ("Evidence Traceability", "Sampled releases fully traceable", m["trace"], "%", "Higher is better"),
        ]
        for dimension, metric, value, unit, note in obs:
            status_dim = "Green"
            if metric == "Commitments met": status_dim = "Green" if value > 95 else ("Amber" if value >= 80 else "Red")
            elif metric == "Failed / rolled-back releases": status_dim = "Green" if value <= 10 else ("Amber" if value <= 20 else "Red")
            elif metric == "SLO compliance":
                status_dim = "Red" if m["critical_slo"] or m["penalty"] else ("Green" if value > 95 else "Amber")
            elif metric == "SLO breach events": status_dim = "Red" if m["critical_slo"] else ("Amber" if value else "Green")
            elif metric == "Penalty exposure": status_dim = "Red" if value > 0 else "Green"
            elif metric == "Material customer signals": status_dim = "Amber" if value else "Green"
            elif metric == "Repeat findings": status_dim = "Green" if value < 10 else ("Amber" if value <= 25 else "Red")
            elif metric == "Overdue actions": status_dim = "Green" if value <= 15 else ("Amber" if value <= 40 else "Red")
            elif metric == "Sampled releases fully traceable": status_dim = "Green" if value > 95 else ("Amber" if value >= 60 else "Red")
            explanation = m["reason"] if status_dim in ("Red", "Amber") else note
            conn.execute("""INSERT INTO observations
              (engagement_id,dimension,metric,value,unit,status,period,evidence_date,confidence,explanation)
              VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (eid, dimension, metric, value, unit, status_dim, "Rolling 90 days", AS_OF.isoformat(), m["confidence"], explanation))
        if eid == "ENG-004":
            conn.execute("""INSERT INTO observations
              (engagement_id,dimension,metric,value,unit,status,period,evidence_date,confidence,explanation)
              VALUES (?,?,?,?,?,?,?,?,?,?)""",
              (eid, "Customer Impact", "Customer feedback coverage", None, "%", "Unknown",
               "Rolling 90 days", AS_OF.isoformat(), "Low", "Synthetic survey feed is unavailable; customer feedback is unassessed, not assumed negative."))

    # Findings: 50 total, 11 repeat, all records synthetic.
    cats = ["Production defect", "Audit observation", "Service incident", "Delivery commitment", "Customer concern"]
    for i in range(50):
        eid = "ENG-007" if i < 5 else ("SRV-012" if i < 10 else ("ENG-014" if i == 10 else ENGAGEMENTS[(i * 3) % len(ENGAGEMENTS)][0]))
        category = "Service incident" if eid == "ENG-021" else cats[i % len(cats)]
        repeat = 1 if i < 11 else 0
        severity = "Critical" if i in (0, 16, 31) else ("High" if i % 7 == 0 else "Moderate")
        summary = ("Synthetic post-release defect leakage; root-cause review required" if eid == "ENG-007" and i == 0 else
                   "Synthetic release evidence item missing or incomplete" if eid == "SRV-012" and i == 5 else
                   "Synthetic critical SLO breach with penalty exposure review" if eid == "ENG-021" and i == 16 else
                   "Synthetic repeat quality finding requiring corrective action" if eid == "ENG-014" and i == 10 else
                   f"Synthetic {category.lower()} observation requiring owner follow-up")
        impact = "Material" if severity == "Critical" else ("Moderate" if i % 4 == 0 else "Low")
        conn.execute("INSERT INTO findings VALUES (?,?,?,?,?,?,?,?,?,1)",
                     (f"F-{i+1:03d}", eid, category, severity, summary, repeat, impact,
                      (AS_OF - timedelta(days=(i % 70))).isoformat(), f"SYN-FIND-{i+1:03d}"))

    # 25 sampled releases, 16 fully traceable; 11 samples for SRV-012 with 7 traceable (63.6%).
    release_engagements = ["SRV-012"] * 11 + ["ENG-007"] * 4 + ["ENG-014", "ENG-004", "ENG-009", "ENG-011", "ENG-013", "ENG-017", "ENG-020", "ENG-025", "ENG-027", "ENG-028", "ENG-001"]
    traceable_indices = set(range(7)) | set(range(11, 20))
    failed_indices = {11}  # 1 of 4 ENG-007 samples = 25% failed/rolled-back.
    for i, eid in enumerate(release_engagements):
        full = 1 if i in traceable_indices else 0
        failed = 1 if i in failed_indices else 0
        approval = 1 if full or i % 3 else 0
        testing = 1 if full or i % 4 else 0
        change = 1 if full or i % 5 else 0
        severity = "High" if failed else "None"
        conn.execute("INSERT INTO releases VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (f"REL-{i+1:03d}", eid, (AS_OF - timedelta(days=(i * 2 % 60))).isoformat(),
                      failed, severity, approval, testing, change, full, f"SYN-REL-EVID-{i+1:03d}"))

    # 29 synthetic actions; exactly 9 are overdue at the as-of date.
    action_specs = [
      ("ENG-007","F-001","Contain release defect leakage and agree temporary go/no-go gate","Engineering Manager · ENG-007",30,"Lower escaped-defect risk before next release","Defect triage and approved gate record","High"),
      ("ENG-007","F-002","Complete cross-functional root-cause review","Delivery Assurance Lead · ENG-007",30,"Document verified causes and control gaps","Signed root-cause review","High"),
      ("ENG-007","REL-012","Add regression coverage for critical failure paths","Engineering Manager · ENG-007",60,"Improve release confidence","Regression suite and run evidence","High"),
      ("ENG-007","F-003","Verify release quality trend after control change","Delivery Assurance Lead · ENG-007",90,"Confirm defect leakage is improving","90-day review record","Medium"),
      ("SRV-012","REL-001","Index missing approval, test, and change evidence","Service Manager · SRV-012",30,"Prepare an auditable release sample","Evidence index and reviewer sign-off","High"),
      ("SRV-012","F-006","Embed evidence capture in the service release workflow","Control Owner · SRV-012",60,"Reduce future evidence gaps","Updated workflow and sample check","Medium"),
      ("SRV-012","REL-007","Re-sample release evidence and verify traceability","Auditor / Control Reviewer · SRV-012",90,"Confirm traceability has improved","Independent sample results","Medium"),
      ("ENG-021","F-017","Restore SLO performance and confirm penalty exposure","Service Manager · ENG-021",30,"Contain customer impact and validate exposure","Incident review and finance confirmation","Critical"),
      ("ENG-014","F-011","Reduce recurring finding backlog","Engineering Manager · ENG-014",60,"Lower repeat quality observations","Closed findings and recurrence review","High"),
    ]
    # Add 20 more portfolio actions with synthetic role owners and linked synthetic findings.
    role_cycle = ["Engineering Manager", "Service Manager", "Delivery Assurance Lead", "Control Owner"]
    for i in range(20):
        eid = ENGAGEMENTS[(i * 5 + 3) % len(ENGAGEMENTS)][0]
        action_specs.append((eid, f"F-{11+i:03d}", f"Review synthetic assurance exception {i+1:02d}",
                             f"{role_cycle[i % len(role_cycle)]} · {eid}", [30,60,90][i%3],
                             "Resolve the linked synthetic risk and improve evidence quality",
                             "Updated evidence and reviewer confirmation", "Medium" if i%3 else "High"))
    for i, spec in enumerate(action_specs):
        eid, trigger, title, owner, horizon, outcome, measure, priority = spec
        overdue = i < 9
        due = AS_OF - timedelta(days=5+i) if overdue else AS_OF + timedelta(days=10 + (i % 3) * 20)
        status = "Overdue" if overdue else (["In progress","Open","Completed"][i % 3])
        completed = "Synthetic closure note pending verification" if status == "Completed" else "Awaiting completion evidence"
        conn.execute("INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
                     (f"ACT-{i+1:03d}", eid, trigger, title, owner, "Delivery team (synthetic)", horizon,
                      due.isoformat(), outcome, measure, priority, status, completed, 0))

    recs = [
      ("REC-001","ENG-007","F-001","Contain release defect leakage before the next production release","Verified 25% failed/rolled-back release rate and high defect leakage support an immediate containment and root-cause review.","Engineering Manager · ENG-007",30,"Reduce customer-facing release risk","Defect triage and approved release gate","High","High"),
      ("REC-002","ENG-007","REL-012","Add targeted regression coverage and verify the next release","A controlled release check can test whether the identified failure paths are addressed.","Engineering Manager · ENG-007",60,"Improve release confidence","Regression evidence and release outcome","High","Medium"),
      ("REC-003","SRV-012","REL-001","Close priority evidence gaps before the audit","SLO performance is stable, but traceability is 64% in the synthetic sample.","Service Manager · SRV-012",30,"Make sampled releases auditable","Evidence index and reviewer sign-off","High","High"),
      ("REC-004","SRV-012","F-006","Add evidence capture to the service release checklist","A repeatable capture step can reduce future missing evidence.","Control Owner · SRV-012",60,"Improve future traceability","Updated workflow and sample check","Medium","Medium"),
      ("REC-005","ENG-021","F-017","Contain the critical SLO breach and confirm penalty exposure","Synthetic records show a critical breach and potential penalty exposure; confirm customer impact and financial treatment.","Service Manager · ENG-021",30,"Restore service and establish confirmed exposure","Incident review plus finance confirmation","Critical","High"),
      ("REC-006","ENG-014","F-011","Run a repeat-finding cause review and assign corrective controls","Repeat observations and overdue actions suggest systemic remediation may be needed.","Engineering Manager · ENG-014",60,"Reduce recurrence","Closed actions and follow-up sample","High","Medium"),
    ]
    for r in recs:
        conn.execute("""INSERT INTO recommendations
          (recommendation_id,engagement_id,trigger_ref,title,rationale,owner,horizon,outcome,success_measure,priority,status,confidence,model_name,synthetic)
          VALUES (?,?,?,?,?,?,?,?,?,?, 'Pending', ?, 'Seeded synthetic draft',1)""", r)


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    _create_schema(conn)
    count = conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0]
    if count == 0:
        _seed(conn)
    conn.commit()
    conn.close()


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def portfolio_summary():
    with connect() as c:
        statuses = {r["overall_status"]: r["n"] for r in c.execute("SELECT overall_status,COUNT(*) n FROM engagements GROUP BY overall_status")}
        totals = c.execute("""SELECT (SELECT COUNT(*) FROM findings) findings,
          (SELECT SUM(repeat_flag) FROM findings) repeats,
          (SELECT COUNT(*) FROM actions) actions,
          (SELECT SUM(CASE WHEN due_date < ? AND status NOT IN ('Completed','Verified') THEN 1 ELSE 0 END) FROM actions) overdue,
          (SELECT COUNT(*) FROM releases) releases,
          (SELECT SUM(fully_traceable) FROM releases) traceable""", (AS_OF.isoformat(),)).fetchone()
        return {"statuses": statuses, "findings": totals["findings"], "repeats": totals["repeats"],
                "actions": totals["actions"], "overdue": totals["overdue"],
                "releases": totals["releases"], "traceable": totals["traceable"]}


def get_engagements(search="", status="All", unit="All"):
    sql = "SELECT * FROM engagements WHERE 1=1"
    args = []
    if search:
        sql += " AND (engagement_id LIKE ? OR name LIKE ? OR business_unit LIKE ?)"
        args.extend([f"%{search}%"] * 3)
    if status != "All": sql += " AND overall_status=?"; args.append(status)
    if unit != "All": sql += " AND business_unit=?"; args.append(unit)
    sql += " ORDER BY CASE overall_status WHEN 'Red' THEN 0 WHEN 'Amber' THEN 1 WHEN 'Unknown' THEN 2 ELSE 3 END, engagement_id"
    with connect() as c: return c.execute(sql, args).fetchall()


def get_engagement(eid):
    with connect() as c:
        return c.execute("SELECT * FROM engagements WHERE engagement_id=?", (eid,)).fetchone()


def get_observations(eid):
    with connect() as c:
        return c.execute("SELECT * FROM observations WHERE engagement_id=? ORDER BY CASE status WHEN 'Red' THEN 0 WHEN 'Amber' THEN 1 WHEN 'Unknown' THEN 2 ELSE 3 END, dimension", (eid,)).fetchall()


def get_actions(horizon=None):
    sql = "SELECT a.*,e.name engagement_name,e.overall_status FROM actions a JOIN engagements e USING(engagement_id)"
    args = []
    if horizon is not None: sql += " WHERE horizon=?"; args.append(horizon)
    sql += " ORDER BY due_date,priority DESC"
    with connect() as c: return c.execute(sql,args).fetchall()


def get_recommendations(status="Pending"):
    sql = "SELECT r.*,e.name engagement_name,e.overall_status FROM recommendations r JOIN engagements e USING(engagement_id)"
    args=[]
    if status != "All": sql += " WHERE r.status=?"; args.append(status)
    sql += " ORDER BY CASE r.priority WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END, r.recommendation_id"
    with connect() as c: return c.execute(sql,args).fetchall()


def get_findings(limit=100):
    with connect() as c:
        return c.execute("SELECT f.*,e.name engagement_name FROM findings f JOIN engagements e USING(engagement_id) ORDER BY CASE severity WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 ELSE 2 END,f.finding_date DESC LIMIT ?", (limit,)).fetchall()


def get_releases():
    with connect() as c:
        return c.execute("SELECT r.*,e.name engagement_name FROM releases r JOIN engagements e USING(engagement_id) ORDER BY release_date DESC,release_id").fetchall()


def approve_recommendation(rec_id):
    with connect() as c:
        rec = c.execute("SELECT * FROM recommendations WHERE recommendation_id=?", (rec_id,)).fetchone()
        if not rec or rec["status"] != "Pending": return False
        due = AS_OF + timedelta(days=rec["horizon"])
        new_id = f"ACT-AI-{rec_id[-3:]}"
        c.execute("""INSERT OR IGNORE INTO actions
          (action_id,engagement_id,trigger_ref,title,owner,contributors,horizon,due_date,expected_outcome,success_measure,priority,status,completion_evidence,verified,synthetic)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,1)""",
          (new_id,rec["engagement_id"],rec["trigger_ref"],rec["title"],rec["owner"],"Delivery team (synthetic)",rec["horizon"],due.isoformat(),rec["outcome"],rec["success_measure"],rec["priority"],"Open","Awaiting completion evidence"))
        c.execute("UPDATE recommendations SET status='Accepted' WHERE recommendation_id=?",(rec_id,))
        c.execute("INSERT INTO recommendation_events (recommendation_id,decision,reviewer,event_time) VALUES (?,?,?,?)",
                  (rec_id,"Accepted","Demo Reviewer",AS_OF.isoformat()))
        return True


def dismiss_recommendation(rec_id):
    with connect() as c:
        c.execute("UPDATE recommendations SET status='Rejected' WHERE recommendation_id=? AND status='Pending'", (rec_id,))
        c.execute("INSERT INTO recommendation_events (recommendation_id,decision,reviewer,event_time) VALUES (?,?,?,?)",
                  (rec_id,"Rejected","Demo Reviewer",AS_OF.isoformat()))


def update_recommendation(rec_id,title,owner,horizon,outcome,measure,priority):
    with connect() as c:
        c.execute("UPDATE recommendations SET title=?,owner=?,horizon=?,outcome=?,success_measure=?,priority=? WHERE recommendation_id=? AND status='Pending'",
                  (title,owner,horizon,outcome,measure,priority,rec_id))
        c.execute("INSERT INTO recommendation_events (recommendation_id,decision,reviewer,event_time) VALUES (?,?,?,?)",
                  (rec_id,"Edited","Demo Reviewer",AS_OF.isoformat()))


def update_action_status(action_id, status):
    with connect() as c:
        row=c.execute("SELECT status FROM actions WHERE action_id=?",(action_id,)).fetchone()
        if not row:return
        c.execute("UPDATE actions SET status=?, verified=? WHERE action_id=?", (status,1 if status=="Verified" else 0,action_id))
        c.execute("INSERT INTO action_events (action_id,from_status,to_status,changed_by,event_time) VALUES (?,?,?,?,?)",
                  (action_id,row["status"],status,"Demo Reviewer",AS_OF.isoformat()))


def average_observation(metric):
    with connect() as c:
        row = c.execute("SELECT AVG(value) avg_value FROM observations WHERE metric=?", (metric,)).fetchone()
        return float(row["avg_value"] or 0)


def action_counts_by_horizon():
    with connect() as c:
        rows = c.execute("SELECT horizon,COUNT(*) n FROM actions GROUP BY horizon").fetchall()
        return {int(r["horizon"]): int(r["n"]) for r in rows}



def get_ai_context(eid):
    with connect() as c:
        engagement = c.execute("SELECT * FROM engagements WHERE engagement_id=?", (eid,)).fetchone()
        observations = c.execute("SELECT * FROM observations WHERE engagement_id=?", (eid,)).fetchall()
        findings = c.execute("SELECT * FROM findings WHERE engagement_id=? ORDER BY finding_date DESC LIMIT 8", (eid,)).fetchall()
        releases = c.execute("SELECT * FROM releases WHERE engagement_id=? ORDER BY release_date DESC LIMIT 8", (eid,)).fetchall()
        actions = c.execute("SELECT * FROM actions WHERE engagement_id=? ORDER BY due_date LIMIT 6", (eid,)).fetchall()
        allowed = [f"OBS-{o['observation_id']}" for o in observations] + [f['finding_id'] for f in findings] + [r['release_id'] for r in releases]
        def plain(rows): return [dict(row) for row in rows]
        return {"engagement": dict(engagement) if engagement else {}, "observations": plain(observations),
                "findings": plain(findings), "release_samples": plain(releases), "existing_actions": plain(actions),
                "allowed_evidence_refs": allowed}


def save_ai_recommendation(eid, rec):
    from datetime import datetime
    rec_id = "REC-AI-" + datetime.now().strftime("%Y%m%d%H%M%S%f")
    trigger = ", ".join(rec["evidence_refs"])
    owner = f"{rec['owner_role']} · {eid}"
    with connect() as c:
        c.execute("""INSERT INTO recommendations
          (recommendation_id,engagement_id,trigger_ref,title,rationale,owner,horizon,outcome,success_measure,priority,status,confidence,model_name,assumptions,synthetic)
          VALUES (?,?,?,?,?,?,?,?,?,?, 'Pending', ?,?,?,1)""",
          (rec_id,eid,trigger,rec["title"],rec["rationale"],owner,rec["horizon_days"],rec["expected_outcome"],rec["success_measure"],rec["priority"],rec["confidence"],rec.get("model","Configured live model"),json.dumps(rec.get("assumptions",[]),ensure_ascii=False)))
    return rec_id
