from __future__ import annotations

import argparse
import html
import json
import sqlite3
import sys
import textwrap
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from types import TracebackType


APP_TITLE = "PS03 Assurance Studio"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ps03_demo.sqlite3"
EXPORT_DIR = BASE_DIR / "exports"
REFERENCE_DATE = date(2026, 11, 5)
PORTFOLIO_BASELINE_HOURS = 240
SEED_VERSION = "6"

BUSINESS_UNITS = [
    "Apex Digital Products",
    "Northwind Modernization",
    "Vector Managed Services",
    "Lumina Enterprise Apps",
    "Summit Quality Office",
]

ROLE_CAPABILITIES = {
    "President / Executive Sponsor": "View the portfolio, review priority decisions, approve interventions, and sponsor escalations.",
    "Delivery Assurance Leader": "Review evidence, challenge ratings, approve or reject AI proposals, and monitor the 90-day pilot.",
    "Engineering Manager": "Update engineering evidence, respond to findings, refine delivery actions, and track closure evidence.",
    "Service Manager": "Update service evidence, respond to SLO risks, maintain action progress, and manage customer-facing safeguards.",
    "Auditor / Control Reviewer": "Inspect evidence traceability, flag control gaps, verify closure evidence, and challenge unsupported claims.",
}

AI_PROVIDERS = [
    "OpenAI-compatible",
    "Azure OpenAI",
    "Anthropic",
    "Local / Offline",
]

DIMENSIONS = [
    "delivery_predictability",
    "release_quality",
    "service_stability",
    "customer_impact",
    "findings_action_health",
    "evidence_traceability",
]

DIMENSION_LABELS = {
    "delivery_predictability": "Delivery Predictability",
    "release_quality": "Release Quality",
    "service_stability": "Service Stability",
    "customer_impact": "Customer Impact",
    "findings_action_health": "Findings & Action Health",
    "evidence_traceability": "Evidence Traceability",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS business_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS engagements (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    business_unit_id INTEGER NOT NULL,
    engagement_type TEXT NOT NULL,
    overall_status TEXT NOT NULL,
    overview_reason TEXT NOT NULL,
    accountable_lead TEXT NOT NULL,
    executive_summary TEXT NOT NULL,
    FOREIGN KEY (business_unit_id) REFERENCES business_units(id)
);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engagement_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    measure_name TEXT NOT NULL,
    measure_value TEXT NOT NULL,
    numerator REAL,
    denominator REAL,
    observation_period TEXT NOT NULL,
    evidence_date TEXT NOT NULL,
    performance_status TEXT NOT NULL,
    evidence_confidence TEXT NOT NULL,
    explanation TEXT NOT NULL,
    critical_override INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL,
    evidence_ref TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (engagement_id) REFERENCES engagements(id)
);

CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY,
    engagement_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    repeat_flag INTEGER NOT NULL,
    evidence_ref TEXT NOT NULL,
    opened_on TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id)
);

CREATE TABLE IF NOT EXISTS releases (
    id TEXT PRIMARY KEY,
    engagement_id TEXT NOT NULL,
    release_name TEXT NOT NULL,
    deployed_on TEXT NOT NULL,
    traceable INTEGER NOT NULL,
    failure_rate REAL NOT NULL,
    verified_incident INTEGER NOT NULL,
    evidence_ref TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id)
);

CREATE TABLE IF NOT EXISTS service_events (
    id TEXT PRIMARY KEY,
    engagement_id TEXT NOT NULL,
    slo_name TEXT NOT NULL,
    target_description TEXT NOT NULL,
    severity TEXT NOT NULL,
    recurrence_count INTEGER NOT NULL,
    customer_impact TEXT NOT NULL,
    assessed_penalty_units REAL NOT NULL,
    estimated_penalty_units REAL NOT NULL,
    evidence_ref TEXT NOT NULL,
    evidence_date TEXT NOT NULL,
    verified INTEGER NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id)
);

CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    engagement_id TEXT NOT NULL,
    title TEXT NOT NULL,
    trigger_ref TEXT NOT NULL,
    accountable_owner TEXT NOT NULL,
    contributors TEXT NOT NULL,
    horizon_days INTEGER NOT NULL,
    due_date TEXT NOT NULL,
    expected_outcome TEXT NOT NULL,
    success_measure TEXT NOT NULL,
    status TEXT NOT NULL,
    escalation_condition TEXT NOT NULL,
    completion_evidence TEXT NOT NULL,
    verified_effectiveness TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id)
);

CREATE TABLE IF NOT EXISTS action_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    evidence TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (action_id) REFERENCES actions(id)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    engagement_id TEXT NOT NULL,
    linked_action_id TEXT,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_summary TEXT NOT NULL,
    proposed_owner TEXT NOT NULL,
    contributors TEXT NOT NULL,
    horizon_days INTEGER NOT NULL,
    due_date TEXT NOT NULL,
    expected_outcome TEXT NOT NULL,
    success_measure TEXT NOT NULL,
    confidence TEXT NOT NULL,
    uncertainty TEXT NOT NULL,
    state TEXT NOT NULL,
    FOREIGN KEY (engagement_id) REFERENCES engagements(id),
    FOREIGN KEY (linked_action_id) REFERENCES actions(id)
);

CREATE TABLE IF NOT EXISTS review_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    previous_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    details TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    FOREIGN KEY (recommendation_id) REFERENCES recommendations(id)
);

CREATE TABLE IF NOT EXISTS pilot_phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_name TEXT NOT NULL,
    day_range TEXT NOT NULL,
    owner TEXT NOT NULL,
    checkpoints TEXT NOT NULL,
    expected_outputs TEXT NOT NULL,
    risks TEXT NOT NULL,
    decision_criteria TEXT NOT NULL
);
"""


def iso(day_text: str) -> str:
    return day_text


def format_status(text: str) -> str:
    return text.replace("_", " ").title()


def format_percentage(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{round(100 * numerator / denominator)}%"


def validate_percentage(value: float | None) -> None:
    if value is not None and not 0 <= value <= 100:
        raise ValueError("Percentage values must be between 0 and 100.")


class ClosingSQLiteConnection(sqlite3.Connection):
    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        try:
            return super().__exit__(exception_type, exception, traceback)
        finally:
            self.close()


def create_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(path, factory=ClosingSQLiteConnection)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def rate_delivery_predictability(value: float | None) -> str:
    validate_percentage(value)
    if value is None:
        return "Unknown"
    if value > 95:
        return "Green"
    if value >= 80:
        return "Amber"
    return "Red"


def rate_evidence_traceability(value: float | None) -> str:
    validate_percentage(value)
    if value is None:
        return "Unknown"
    if value > 95:
        return "Green"
    if value >= 60:
        return "Amber"
    return "Red"


def rate_release_failure(
    value: float | None, verified_severity_1_incident: bool = False
) -> str:
    validate_percentage(value)
    if value is None:
        return "Unknown"
    if verified_severity_1_incident or value > 20:
        return "Red"
    if value > 10:
        return "Amber"
    return "Green"


def rate_slo_compliance(
    value: float | None,
    *,
    verified: bool = True,
    critical_breach: bool = False,
    repeated_breach: bool = False,
    material_assessed_penalty: bool = False,
    isolated_noncritical_breach: bool = False,
) -> str:
    validate_percentage(value)
    if value is None or not verified:
        return "Unknown"
    if critical_breach or repeated_breach or material_assessed_penalty:
        return "Red"
    if value <= 95 or isolated_noncritical_breach:
        return "Amber"
    return "Green"


def rate_service_stability(
    compliance_percent: float | None,
    breach_severity: str | None = None,
    recurrence_count: int = 0,
    assessed_penalty_units: float = 0,
    *,
    evidence_verified: bool = True,
) -> str:
    return rate_slo_compliance(
        compliance_percent,
        verified=evidence_verified,
        critical_breach=breach_severity == "Critical",
        repeated_breach=recurrence_count > 1,
        material_assessed_penalty=assessed_penalty_units > 0,
        isolated_noncritical_breach=(
            breach_severity == "Noncritical" and recurrence_count == 1
        ),
    )


def rate_repeat_findings(value: float | None) -> str:
    validate_percentage(value)
    if value is None:
        return "Unknown"
    if value > 25:
        return "Red"
    if value >= 10:
        return "Amber"
    return "Green"


def rate_overdue_actions(value: float | None) -> str:
    validate_percentage(value)
    if value is None:
        return "Unknown"
    if value > 40:
        return "Red"
    if value > 15:
        return "Amber"
    return "Green"


def can_review_recommendations(role: str) -> bool:
    return role in {
        "President / Executive Sponsor",
        "Delivery Assurance Leader",
    }


RATING_ASSUMPTIONS = (
    "Contest-demo assumptions only; these are not industry or contract standards.",
    "Delivery predictability: Green >95%; Amber 80–95%; Red <80%.",
    "Evidence traceability: Green >95%; Amber 60–95%; Red <60%.",
    "SLO compliance: Green >95% with no material breach or assessed penalty; "
    "Amber at or below 95% or with an isolated noncritical breach; Red for a "
    "critical/repeated breach or material assessed penalty.",
    "Failed/rolled-back production releases: Green ≤10%; Amber >10–20%; "
    "Red >20%; a verified severity 1 customer-impacting incident is Red.",
    "Repeat findings: Green <10%; Amber 10–25%; Red >25%.",
    "Overdue actions: Green ≤15%; Amber >15–40%; Red >40%.",
    "Findings & action health uses the worse verified result of repeat findings "
    "or overdue actions; customer impact uses documented severity/recurrence "
    "because no numeric band was supplied.",
    "Estimated penalty exposure is shown for review; a verified material assessed "
    "penalty is a Red service-stability trigger.",
    "Missing, stale, or unverified evidence is Unknown for the affected measure.",
)


def seed_database(reset: bool = False, path: Path = DB_PATH) -> None:
    if reset and path.exists():
        path.unlink()

    with create_connection(path) as connection:
        connection.executescript(SCHEMA)
        seeded = connection.execute(
            "SELECT value FROM settings WHERE key = 'seed_version'"
        ).fetchone()
        if seeded and seeded["value"] == SEED_VERSION:
            return
        if seeded:
            if seeded["value"] not in {"1", "2", "3", "4", "5"}:
                raise RuntimeError(
                    f"Unsupported seed version {seeded['value']}; use --reset-db only if the demo database may be rebuilt."
                )
            if seeded["value"] in {"1", "2", "3", "4", "5"}:
                connection.execute(
                    """
                    UPDATE service_events
                    SET id = 'SLO-007-001', evidence_ref = 'SLO-EV-007-001'
                    WHERE id = 'SLO-009-001' AND engagement_id = 'SRV-007'
                    """
                )
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO service_events(
                        id, engagement_id, slo_name, target_description, severity,
                        recurrence_count, customer_impact, assessed_penalty_units,
                        estimated_penalty_units, evidence_ref, evidence_date, verified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    build_service_events(),
                )
                connection.execute(
                    """
                    UPDATE observations
                    SET performance_status = 'Red',
                        explanation = 'Repeat findings exceed the assumed Red band, with overdue actions further increasing control risk.'
                    WHERE engagement_id = 'ENG-007'
                      AND dimension = 'findings_action_health'
                      AND measure_value = '26% repeat findings; 31% overdue actions'
                    """
                )
            if seeded["value"] == "1":
                connection.execute(
                    """
                    UPDATE actions SET status = 'Draft'
                    WHERE id IN (
                        SELECT r.linked_action_id
                        FROM recommendations r
                        WHERE r.state = 'Pending Human Review'
                          AND r.linked_action_id IS NOT NULL
                    ) AND status IN ('In Progress', 'Approved')
                    """
                )
            if seeded["value"] in {"1", "2", "3"}:
                connection.execute(
                    """
                    UPDATE actions
                    SET status = 'Owner Reported Complete'
                    WHERE status = 'Completed'
                    """
                )
            observation_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(observations)")
            }
            if "evidence_ref" not in observation_columns:
                connection.execute(
                    "ALTER TABLE observations ADD COLUMN evidence_ref TEXT NOT NULL DEFAULT ''"
                )
            connection.execute(
                """
                UPDATE observations
                SET evidence_ref = 'SYN-' || engagement_id || '-' || UPPER(dimension)
                WHERE evidence_ref = ''
                """
            )
            connection.execute(
                """
                UPDATE actions
                SET verified_effectiveness =
                    'Synthetic independent review record: linked evidence and success measure checked.'
                WHERE status = 'Verified' AND verified_effectiveness = 'Verified'
                """
            )
            connection.execute(
                "UPDATE settings SET value = ? WHERE key = 'seed_version'",
                (SEED_VERSION,),
            )
            for engagement in connection.execute("SELECT id FROM engagements"):
                observations = list(
                    connection.execute(
                        "SELECT * FROM observations WHERE engagement_id = ? ORDER BY sort_order",
                        (engagement["id"],),
                    )
                )
                status, reason = derive_overall_status(observations)
                connection.execute(
                    "UPDATE engagements SET overall_status = ?, overview_reason = ? WHERE id = ?",
                    (status, reason, engagement["id"]),
                )
            return
        existing_engagements = connection.execute(
            "SELECT COUNT(*) AS count FROM engagements"
        ).fetchone()["count"]
        if existing_engagements:
            raise RuntimeError(
                "The database contains unversioned records and was not changed. "
                "Back it up before using --reset-db."
            )

        for table_name in [
            "review_events",
            "recommendations",
            "action_events",
            "actions",
            "service_events",
            "releases",
            "findings",
            "observations",
            "engagements",
            "pilot_phases",
            "business_units",
            "settings",
        ]:
            connection.execute(f"DELETE FROM {table_name}")

        connection.executemany(
            "INSERT INTO business_units(name) VALUES (?)",
            [(name,) for name in BUSINESS_UNITS],
        )

        business_unit_ids = {
            row["name"]: row["id"]
            for row in connection.execute("SELECT id, name FROM business_units")
        }

        engagements = build_engagements()
        observations = build_observations(engagements)
        observations_by_engagement: dict[str, list[dict[str, object]]] = {}
        for observation in observations:
            observations_by_engagement.setdefault(observation[0], []).append(
                {
                    "dimension": observation[1],
                    "performance_status": observation[8],
                    "evidence_confidence": observation[9],
                    "critical_override": observation[11],
                }
            )
        for engagement in engagements:
            status, reason = derive_overall_status(
                observations_by_engagement[engagement["id"]]
            )
            engagement["overall_status"] = status
            engagement["overview_reason"] = reason

        connection.executemany(
            """
            INSERT INTO engagements(
                id, name, business_unit_id, engagement_type, overall_status,
                overview_reason, accountable_lead, executive_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    item["id"],
                    item["name"],
                    business_unit_ids[item["business_unit"]],
                    item["engagement_type"],
                    item["overall_status"],
                    item["overview_reason"],
                    item["accountable_lead"],
                    item["executive_summary"],
                )
                for item in engagements
            ],
        )

        connection.executemany(
            """
            INSERT INTO observations(
                engagement_id, dimension, measure_name, measure_value, numerator,
                denominator, observation_period, evidence_date, performance_status,
                evidence_confidence, explanation, critical_override, sort_order,
                evidence_ref
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            observations,
        )

        findings = build_findings([item["id"] for item in engagements])
        connection.executemany(
            """
            INSERT INTO findings(
                id, engagement_id, title, category, severity, status, repeat_flag,
                evidence_ref, opened_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            findings,
        )

        releases = build_releases([item["id"] for item in engagements])
        connection.executemany(
            """
            INSERT INTO releases(
                id, engagement_id, release_name, deployed_on, traceable,
                failure_rate, verified_incident, evidence_ref
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            releases,
        )

        service_events = build_service_events()
        connection.executemany(
            """
            INSERT INTO service_events(
                id, engagement_id, slo_name, target_description, severity,
                recurrence_count, customer_impact, assessed_penalty_units,
                estimated_penalty_units, evidence_ref, evidence_date, verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            service_events,
        )

        actions = build_actions([item["id"] for item in engagements])
        connection.executemany(
            """
            INSERT INTO actions(
                id, engagement_id, title, trigger_ref, accountable_owner,
                contributors, horizon_days, due_date, expected_outcome,
                success_measure, status, escalation_condition,
                completion_evidence, verified_effectiveness
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            actions,
        )

        recommendations = build_recommendations()
        connection.executemany(
            """
            INSERT INTO recommendations(
                id, engagement_id, linked_action_id, title, rationale,
                evidence_summary, proposed_owner, contributors, horizon_days,
                due_date, expected_outcome, success_measure, confidence,
                uncertainty, state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            recommendations,
        )

        connection.executemany(
            """
            INSERT INTO pilot_phases(
                phase_name, day_range, owner, checkpoints, expected_outputs,
                risks, decision_criteria
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            build_pilot_phases(),
        )

        connection.executemany(
            "INSERT INTO settings(key, value) VALUES (?, ?)",
            [
                ("seed_version", SEED_VERSION),
                ("portfolio_baseline_hours", str(PORTFOLIO_BASELINE_HOURS)),
                ("current_role", list(ROLE_CAPABILITIES)[1]),
                ("ai_provider", AI_PROVIDERS[0]),
                ("reference_date", REFERENCE_DATE.isoformat()),
            ],
        )


def build_engagements() -> list[dict[str, str]]:
    rows = []
    engineering_names = [
        "Northstar Commerce Platform",
        "Atlas Claims Modernization",
        "Summit Loyalty Engineering",
        "Beacon Order Services",
        "Orion Pricing Accelerator",
        "Cobalt Device Cloud",
        "Meridian Checkout Engineering",
        "Delta Billing API",
        "Harbor Data Migration",
        "Nimbus Experience Factory",
        "Terra Risk Portal",
        "Nova Policy Workbench",
        "Quasar Supply Integrations",
        "Forge Release Train",
        "Echo Mobile Suite",
        "Zenith Partner Enablement",
    ]
    service_names = [
        "Helios Retail Support",
        "Cascade ERP Operations",
        "Bluewave Application Support",
        "Citrine Incident Command",
        "Evergreen Platform Reliability",
        "Matrix Service Desk",
        "Pioneer Managed Run",
        "Signal Command Centre",
        "Granite Core Services",
        "Vector Claims Operations",
        "Astra Managed Support",
        "Pulse Care Operations",
    ]

    overall_map = {
        "ENG-001": "Green",
        "ENG-002": "Green",
        "ENG-003": "Green",
        "ENG-004": "Green",
        "ENG-005": "Green",
        "ENG-006": "Green",
        "ENG-007": "Red",
        "ENG-008": "Green",
        "ENG-009": "Amber",
        "ENG-010": "Green",
        "ENG-011": "Green",
        "ENG-012": "Amber",
        "ENG-013": "Green",
        "ENG-014": "Red",
        "ENG-015": "Green",
        "ENG-016": "Green",
        "SRV-001": "Green",
        "SRV-002": "Amber",
        "SRV-003": "Green",
        "SRV-004": "Red",
        "SRV-005": "Green",
        "SRV-006": "Amber",
        "SRV-007": "Amber",
        "SRV-008": "Amber",
        "SRV-009": "Red",
        "SRV-010": "Amber",
        "SRV-011": "Amber",
        "SRV-012": "Amber",
    }

    reasons = {
        "Green": "All six dimensions are evidence-backed Green with no material override.",
        "Amber": "At least one dimension needs leadership attention, but no verified critical Red override is present.",
        "Red": "A verified critical dimension is Red and requires immediate executive intervention.",
    }

    for index, name in enumerate(engineering_names, start=1):
        engagement_id = f"ENG-{index:03d}"
        status = overall_map[engagement_id]
        rows.append(
            {
                "id": engagement_id,
                "name": name,
                "business_unit": BUSINESS_UNITS[(index - 1) % len(BUSINESS_UNITS)],
                "engagement_type": "Engineering",
                "overall_status": status,
                "overview_reason": reasons[status],
                "accountable_lead": "Engineering Manager",
                "executive_summary": build_engagement_summary(engagement_id, status),
            }
        )

    for index, name in enumerate(service_names, start=1):
        engagement_id = f"SRV-{index:03d}"
        status = overall_map[engagement_id]
        rows.append(
            {
                "id": engagement_id,
                "name": name,
                "business_unit": BUSINESS_UNITS[(index + 1) % len(BUSINESS_UNITS)],
                "engagement_type": "Service",
                "overall_status": status,
                "overview_reason": reasons[status],
                "accountable_lead": "Service Manager",
                "executive_summary": build_engagement_summary(engagement_id, status),
            }
        )

    return rows


def build_engagement_summary(engagement_id: str, status: str) -> str:
    if engagement_id == "ENG-007":
        return (
            "Synthetic engineering example: milestone predictability remains Green, but verified "
            "release failure and defect leakage drive an overall Red assurance position."
        )
    if engagement_id == "SRV-012":
        return (
            "Synthetic service example: service stability is Green, yet evidence traceability is "
            "Amber because only 16 of 25 sampled release-control artifacts are fully traceable."
        )
    if status == "Green":
        return (
            "Synthetic engagement operating within the expected assurance guardrails with clear "
            "evidence, current actions, and no unresolved critical override."
        )
    if status == "Amber":
        return (
            "Synthetic engagement needing follow-up on one or more dimensions such as evidence "
            "traceability, action timeliness, or customer impact."
        )
    return (
        "Synthetic engagement with a verified critical issue requiring direct leadership attention, "
        "named ownership, and a near-term decision checkpoint."
    )


def observation_row(
    engagement_id: str,
    dimension: str,
    measure_name: str,
    measure_value: str,
    numerator: float | None,
    denominator: float | None,
    performance_status: str,
    evidence_confidence: str,
    explanation: str,
    sort_order: int,
    critical_override: int = 0,
) -> tuple:
    return (
        engagement_id,
        dimension,
        measure_name,
        measure_value,
        numerator,
        denominator,
        "Latest 30 days",
        "2026-11-03",
        performance_status,
        evidence_confidence,
        explanation,
        critical_override,
        sort_order,
        f"SYN-{engagement_id}-{dimension.upper()}",
    )


def build_green_observations(engagement_id: str) -> list[tuple]:
    return [
        observation_row(
            engagement_id,
            "delivery_predictability",
            "Milestones delivered on time",
            "97%",
            97,
            100,
            "Green",
            "Verified",
            "Delivery commitments were met consistently across the latest reporting period.",
            1,
        ),
        observation_row(
            engagement_id,
            "release_quality",
            "Failed or rolled-back production releases",
            "8%",
            8,
            100,
            "Green",
            "Verified",
            "Release quality remains within the assumed Green band and no severity 1 incident was verified.",
            2,
        ),
        observation_row(
            engagement_id,
            "service_stability",
            "Applicable SLO measurements met",
            "98%",
            98,
            100,
            "Green",
            "Verified",
            "Service stability is operating above the assumed Green threshold with no material breach.",
            3,
        ),
        observation_row(
            engagement_id,
            "customer_impact",
            "Material customer escalations",
            "0 material escalations",
            0,
            1,
            "Green",
            "Verified",
            "No verified material customer impact was raised in the current period.",
            4,
        ),
        observation_row(
            engagement_id,
            "findings_action_health",
            "Repeat findings / overdue actions",
            "8% repeat findings; 12% overdue actions",
            8,
            100,
            "Green",
            "Verified",
            "Findings are closing within the assumed range and overdue actions remain controlled.",
            5,
        ),
        observation_row(
            engagement_id,
            "evidence_traceability",
            "Sampled releases fully traceable",
            "96%",
            24,
            25,
            "Green",
            "Verified",
            "Release approvals, test evidence, and change records remain traceable end to end.",
            6,
        ),
    ]


def build_amber_observations(engagement_id: str, engagement_type: str) -> list[tuple]:
    base = build_green_observations(engagement_id)
    if engagement_id == "ENG-009":
        base[0] = observation_row(
            engagement_id,
            "delivery_predictability",
            "Milestones delivered on time",
            "89%",
            89,
            100,
            "Amber",
            "Verified",
            "Delivery predictability has slipped into the assumed Amber band and needs plan correction.",
            1,
        )
    elif engagement_id == "ENG-012":
        base[4] = observation_row(
            engagement_id,
            "findings_action_health",
            "Repeat findings / overdue actions",
            "18% repeat findings; 27% overdue actions",
            27,
            100,
            "Amber",
            "Verified",
            "Corrective actions are not yet closing fast enough to support a Green posture.",
            5,
        )
    elif engagement_id == "SRV-002":
        base[3] = observation_row(
            engagement_id,
            "customer_impact",
            "Material customer escalations",
            "2 recurring executive complaints",
            2,
            10,
            "Amber",
            "Verified",
            "Service KPIs are stable, but recurring customer complaints require targeted follow-up.",
            4,
        )
    elif engagement_id == "SRV-006":
        base[5] = observation_row(
            engagement_id,
            "evidence_traceability",
            "Sampled releases fully traceable",
            "Unknown - stale approval pack",
            None,
            None,
            "Unknown",
            "Unknown",
            "Evidence is stale for the sampled release pack, so assurance remains Amber until refreshed evidence is supplied.",
            6,
        )
    elif engagement_id == "SRV-007":
        base[2] = observation_row(
            engagement_id,
            "service_stability",
            "Applicable SLO measurements met",
            "95%",
            95,
            100,
            "Amber",
            "Verified",
            "Service stability sits on the threshold and includes one isolated, noncritical breach.",
            3,
        )
    elif engagement_id == "SRV-008":
        base[4] = observation_row(
            engagement_id,
            "findings_action_health",
            "Repeat findings / overdue actions",
            "24% repeat findings; 18% overdue actions",
            24,
            100,
            "Amber",
            "Verified",
            "Findings are recurring too often to support a Green assurance view.",
            5,
        )
    elif engagement_id == "SRV-010":
        base[3] = observation_row(
            engagement_id,
            "customer_impact",
            "Material customer escalations",
            "1 unresolved service concern",
            1,
            10,
            "Amber",
            "Partial",
            "Customer outcomes are recoverable, but the concern remains unresolved this month.",
            4,
        )
    elif engagement_id == "SRV-011":
        base[0] = observation_row(
            engagement_id,
            "delivery_predictability",
            "Milestones delivered on time",
            "84%",
            84,
            100,
            "Amber",
            "Verified",
            "Transition milestones are slipping and need owner-led correction over the next 30 days.",
            1,
        )
    elif engagement_id == "SRV-012":
        return [
            observation_row(
                engagement_id,
                "delivery_predictability",
                "Milestones delivered on time",
                "96%",
                96,
                100,
                "Green",
                "Verified",
                "Delivery predictability remains above the assumed Green threshold.",
                1,
            ),
            observation_row(
                engagement_id,
                "release_quality",
                "Failed or rolled-back production releases",
                "8%",
                8,
                100,
                "Green",
                "Verified",
                "Release outcomes are stable and below the assumed Amber threshold.",
                2,
            ),
            observation_row(
                engagement_id,
                "service_stability",
                "Applicable SLO measurements met",
                "99% with no material breach or penalty",
                99,
                100,
                "Green",
                "Verified",
                "The service engagement is performing strongly against its applicable SLOs.",
                3,
            ),
            observation_row(
                engagement_id,
                "customer_impact",
                "Material customer escalations",
                "0 material escalations",
                0,
                1,
                "Green",
                "Verified",
                "Customers are not experiencing verified material service harm in the latest review period.",
                4,
            ),
            observation_row(
                engagement_id,
                "findings_action_health",
                "Repeat findings / overdue actions",
                "9% repeat findings; 14% overdue actions",
                9,
                100,
                "Green",
                "Verified",
                "Corrective actions are mostly on time and repeat findings remain controlled.",
                5,
            ),
            observation_row(
                engagement_id,
                "evidence_traceability",
                "Sampled releases fully traceable",
                "64% (16 of 25 synthetic samples)",
                16,
                25,
                "Amber",
                "Verified",
                "Evidence traceability is incomplete even though the service is stable, so the overall rating remains Amber.",
                6,
            ),
        ]

    if engagement_type == "Engineering":
        base[5] = observation_row(
            engagement_id,
            "evidence_traceability",
            "Sampled releases fully traceable",
            "91%",
            23,
            25,
            "Amber",
            "Partial",
            "Evidence traceability is close to Green but still below the assumed threshold.",
            6,
        )
    return base


def build_red_observations(engagement_id: str, engagement_type: str) -> list[tuple]:
    if engagement_id == "ENG-007":
        return [
            observation_row(
                engagement_id,
                "delivery_predictability",
                "Milestones delivered on time",
                "97%",
                97,
                100,
                "Green",
                "Verified",
                "Milestone delivery looks healthy in isolation.",
                1,
            ),
            observation_row(
                engagement_id,
                "release_quality",
                "Failed or rolled-back production releases",
                "25% with verified high defect leakage",
                25,
                100,
                "Red",
                "Verified",
                "Release quality is Red because failed releases exceed the assumed Red band and defect leakage is verified.",
                2,
                1,
            ),
            observation_row(
                engagement_id,
                "service_stability",
                "Post-release incident stability",
                "92% stable",
                92,
                100,
                "Amber",
                "Verified",
                "Stability degraded after release events, but the critical override already comes from release quality.",
                3,
            ),
            observation_row(
                engagement_id,
                "customer_impact",
                "Material customer escalations",
                "2 critical business complaints",
                2,
                10,
                "Amber",
                "Verified",
                "Customer impact is visible and reinforces the need for immediate recovery actions.",
                4,
            ),
            observation_row(
                engagement_id,
                "findings_action_health",
                "Repeat findings / overdue actions",
                "26% repeat findings; 31% overdue actions",
                31,
                100,
                "Red",
                "Verified",
                "Repeat findings exceed the assumed Red band, with overdue actions further increasing control risk.",
                5,
            ),
            observation_row(
                engagement_id,
                "evidence_traceability",
                "Sampled releases fully traceable",
                "96%",
                24,
                25,
                "Green",
                "Verified",
                "Evidence quality is not the issue; the failure signal is performance-based and verified.",
                6,
            ),
        ]

    if engagement_type == "Engineering":
        return [
            observation_row(
                engagement_id,
                "delivery_predictability",
                "Milestones delivered on time",
                "78%",
                78,
                100,
                "Red",
                "Verified",
                "Delivery predictability has moved below the assumed Red threshold.",
                1,
                1,
            ),
            observation_row(
                engagement_id,
                "release_quality",
                "Failed or rolled-back production releases",
                "18%",
                18,
                100,
                "Amber",
                "Verified",
                "Release quality is degraded, but the Red override comes from missed commitments.",
                2,
            ),
            observation_row(
                engagement_id,
                "service_stability",
                "Post-release incident stability",
                "90% stable",
                90,
                100,
                "Amber",
                "Partial",
                "Incident evidence shows pressure on the live environment after recent changes.",
                3,
            ),
            observation_row(
                engagement_id,
                "customer_impact",
                "Material customer escalations",
                "1 executive escalation",
                1,
                10,
                "Amber",
                "Verified",
                "Customers are now seeing milestone slips and unresolved quality risk.",
                4,
            ),
            observation_row(
                engagement_id,
                "findings_action_health",
                "Repeat findings / overdue actions",
                "21% repeat findings; 33% overdue actions",
                33,
                100,
                "Amber",
                "Verified",
                "Actions are not closing fast enough to contain the delivery issue.",
                5,
            ),
            observation_row(
                engagement_id,
                "evidence_traceability",
                "Sampled releases fully traceable",
                "92%",
                23,
                25,
                "Amber",
                "Partial",
                "Evidence quality is acceptable but still short of the assumed Green threshold.",
                6,
            ),
        ]

    return [
        observation_row(
            engagement_id,
            "delivery_predictability",
            "Milestones delivered on time",
            "93%",
            93,
            100,
            "Amber",
            "Verified",
            "Planned service improvements are slipping while leadership attention is on stability risks.",
            1,
        ),
        observation_row(
            engagement_id,
            "release_quality",
            "Failed or rolled-back production releases",
            "12%",
            12,
            100,
            "Amber",
            "Verified",
            "Release quality is pressured but not the primary Red override.",
            2,
        ),
        observation_row(
            engagement_id,
            "service_stability",
            "Applicable SLO measurements met",
            "91% with repeated critical breach",
            91,
            100,
            "Red",
            "Verified",
            "A repeated critical SLO breach moves service stability to Red under the assumed rule set.",
            3,
            1,
        ),
        observation_row(
            engagement_id,
            "customer_impact",
            "Material customer escalations",
            "3 material service complaints",
            3,
            10,
            "Red",
            "Verified",
            "Customer impact is already material and evidence-backed.",
            4,
            1,
        ),
        observation_row(
            engagement_id,
            "findings_action_health",
            "Repeat findings / overdue actions",
            "29% repeat findings; 41% overdue actions",
            41,
            100,
            "Red",
            "Verified",
            "Corrective action health is also Red and reinforces the need for escalation.",
            5,
            1,
        ),
        observation_row(
            engagement_id,
            "evidence_traceability",
            "Sampled releases fully traceable",
            "82%",
            20,
            25,
            "Amber",
            "Partial",
            "Traceability is incomplete, but the main leadership concern is the verified service breach.",
            6,
        ),
    ]


def build_observations(engagements: list[dict[str, str]]) -> list[tuple]:
    rows: list[tuple] = []
    for engagement in engagements:
        status = engagement["overall_status"]
        engagement_id = engagement["id"]
        engagement_type = engagement["engagement_type"]
        if status == "Green":
            rows.extend(build_green_observations(engagement_id))
        elif status == "Amber":
            rows.extend(build_amber_observations(engagement_id, engagement_type))
        else:
            rows.extend(build_red_observations(engagement_id, engagement_type))
    return rows


def build_findings(engagement_ids: list[str]) -> list[tuple]:
    categories = [
        "Defect Leakage",
        "Audit Evidence",
        "SLO Control",
        "Delivery Milestone",
        "Customer Escalation",
    ]
    severities = ["High", "Medium", "Medium", "Low", "High"]
    statuses = ["Open", "Closed", "In Review", "Closed", "Open"]
    rows = []
    for index in range(50):
        engagement_id = engagement_ids[index % len(engagement_ids)]
        if index < 4:
            engagement_id = "ENG-007"
        elif index == 4:
            engagement_id = "SRV-012"
        elif index in {18, 19, 20}:
            engagement_id = "SRV-004"
        elif index in {31, 32}:
            engagement_id = "ENG-014"
        category = categories[index % len(categories)]
        rows.append(
            (
                f"FND-{index + 1:03d}",
                engagement_id,
                f"Synthetic {category.lower()} finding {index + 1}",
                category,
                severities[index % len(severities)],
                statuses[index % len(statuses)],
                1 if index < 11 else 0,
                f"EV-{index + 1:03d}",
                iso(f"2026-10-{(index % 28) + 1:02d}"),
            )
        )
    return rows


def build_releases(engagement_ids: list[str]) -> list[tuple]:
    rows = []
    traceable_ids = set(range(1, 17))
    for index in range(25):
        if index < 4:
            engagement_id = "ENG-007"
        elif 4 <= index < 7:
            engagement_id = "SRV-012"
        elif 7 <= index < 10:
            engagement_id = "SRV-004"
        else:
            engagement_id = engagement_ids[index % len(engagement_ids)]
        traceable = 1 if (index + 1) in traceable_ids else 0
        failure_rate = 25.0 if engagement_id == "ENG-007" and index == 0 else 8.0 + (index % 5) * 2
        verified_incident = 1 if engagement_id in {"SRV-004", "SRV-009"} and index % 3 == 0 else 0
        rows.append(
            (
                f"REL-{index + 1:03d}",
                engagement_id,
                f"Synthetic release sample {index + 1}",
                iso(f"2026-10-{(index % 25) + 1:02d}"),
                traceable,
                failure_rate,
                verified_incident,
                f"TRACE-{index + 1:03d}",
            )
        )
    return rows


def build_service_events() -> list[tuple]:
    return [
        (
            "SLO-012-001",
            "SRV-012",
            "Service availability",
            "Synthetic applicable target: 99% of target measurements met",
            "None",
            0,
            "No material customer impact recorded",
            0,
            0,
            "SLO-EV-012-001",
            "2026-11-03",
            1,
        ),
        (
            "SLO-004-001",
            "SRV-004",
            "Core transaction availability",
            "Synthetic target miss across three reporting periods",
            "Critical",
            3,
            "Synthetic interruption to a critical customer workflow",
            0,
            12000,
            "SLO-EV-004-001",
            "2026-11-02",
            1,
        ),
        (
            "SLO-007-001",
            "SRV-007",
            "Response-time objective",
            "One isolated noncritical breach in the latest period",
            "Noncritical",
            1,
            "No material customer impact verified",
            0,
            2500,
            "SLO-EV-007-001",
            "2026-11-01",
            1,
        ),
        (
            "SLO-009-002",
            "SRV-009",
            "Core service availability",
            "Synthetic target miss across two reporting periods",
            "Critical",
            2,
            "Synthetic recurring interruption with material customer impact",
            3000,
            6000,
            "SLO-EV-009-002",
            "2026-11-02",
            1,
        ),
    ]


def build_actions(engagement_ids: list[str]) -> list[tuple]:
    special = {
        0: (
            "ACT-001",
            "ENG-007",
            "Stabilize release exit criteria and defect triage",
            "FND-001",
            "Engineering Manager",
            "Delivery Assurance Leader, Test Lead",
            30,
            "2026-11-18",
            "No further releases proceed without evidence-backed exit criteria and daily defect review.",
            "Failed or rolled-back production releases return below 10% in the next release cycle.",
            "Draft",
            "Escalate immediately if another release rollback is required.",
            "Signed release checklist, triage log, and defect-burn evidence.",
            "Pending independent verification",
        ),
        1: (
            "ACT-002",
            "SRV-012",
            "Close release-control traceability gaps",
            "FND-005",
            "Service Manager",
            "Auditor / Control Reviewer, Change Lead",
            60,
            "2026-12-12",
            "The sampled release evidence pack becomes fully traceable for audit review.",
            "Traceability improves from 64% to at least 90% in the pilot sample.",
            "Draft",
            "Escalate if the next audit sample still contains unlinked approvals or missing records.",
            "Complete control pack, linked approvals, and audit-ready release map.",
            "Owner-reported completion only",
        ),
        2: (
            "ACT-003",
            "SRV-004",
            "Contain repeated critical SLO breaches",
            "FND-019",
            "Service Manager",
            "President / Executive Sponsor, Delivery Assurance Leader",
            30,
            "2026-11-12",
            "Critical breach recurrence is contained and customer recovery communication is active.",
            "No repeated critical SLO breach is recorded for two consecutive reporting cycles.",
            "Draft",
            "Escalate immediately on any additional material penalty exposure.",
            "Breach root-cause pack, corrective implementation record, and sponsor update.",
            "Pending independent verification",
        ),
    }
    rows = []
    overdue_indexes = {3, 4, 5, 8, 9, 10, 13, 14, 15}
    overdue_statuses = ["Draft", "Approved", "In Progress"]
    on_track_statuses = [
        "Approved",
        "In Progress",
        "Owner Reported Complete",
        "Verified",
    ]
    overdue_dates = ["2026-10-11", "2026-10-18", "2026-10-24", "2026-10-29"]
    future_dates = ["2026-11-12", "2026-11-18", "2026-11-22", "2026-12-04", "2026-12-19", "2027-01-07"]
    for index in range(29):
        if index in special:
            rows.append(special[index])
            continue

        engagement_id = engagement_ids[(index + 3) % len(engagement_ids)]
        horizon = [30, 60, 90][index % 3]
        if index in overdue_indexes:
            due_date = overdue_dates[index % len(overdue_dates)]
            status = overdue_statuses[index % len(overdue_statuses)]
        else:
            due_date = future_dates[index % len(future_dates)]
            status = on_track_statuses[index % len(on_track_statuses)]
        rows.append(
            (
                f"ACT-{index + 1:03d}",
                engagement_id,
                f"Synthetic action {index + 1}",
                f"FND-{((index * 2) % 50) + 1:03d}",
                "Engineering Manager" if engagement_id.startswith("ENG") else "Service Manager",
                "Delivery Assurance Leader, Auditor / Control Reviewer",
                horizon,
                due_date,
                "Reduce the triggering risk and provide evidence-backed closure.",
                "Action is completed on time with evidence retained and independently reviewed.",
                status,
                "Escalate if due date slips or customer impact worsens.",
                "Linked evidence pack and owner commentary.",
                (
                    "Auditor confirmed the linked evidence and success measure."
                    if status == "Verified"
                    else "Awaiting independent verification"
                ),
            )
        )

    return rows


def build_recommendations() -> list[tuple]:
    return [
        (
            "REC-001",
            "ENG-007",
            "ACT-001",
            "Tighten release-readiness controls before the next deployment",
            "The recommendation is triggered by Green milestone delivery masking a Red release-quality outcome.",
            "Evidence: REL-001 (25% failed/rolled-back sample, 2026-10-01), FND-001 "
            "(verified defect leakage, 2026-10-01), and ENG-007 observations "
            "(as of 2026-11-03).",
            "Engineering Manager",
            "Delivery Assurance Leader, Test Lead",
            30,
            "2026-11-18",
            "Re-establish evidence-backed release gates and contain defect leakage.",
            "Failed releases return below 10% with explicit approver sign-off.",
            "High",
            "The AI can explain the pattern but cannot guarantee which recovery sequence is best without human approval.",
            "Pending Human Review",
        ),
        (
            "REC-002",
            "SRV-012",
            "ACT-002",
            "Repair evidence traceability without downgrading stable service performance",
            "Stable SLO performance is verified, but the audit sample remains incomplete.",
            "Evidence: SLO-EV-012-001 (verified SLO record, 2026-11-03), "
            "FND-005 (evidence control observation, 2026-10-05), and the "
            "synthetic release sample (16/25 traceable, 2026-11-03).",
            "Service Manager",
            "Auditor / Control Reviewer, Change Lead",
            60,
            "2026-12-12",
            "Provide a complete and current evidence chain for sampled releases.",
            "Traceability reaches at least 90% in the next audit sample.",
            "Medium",
            "The recommendation assumes missing evidence is a control issue, not a service-performance issue.",
            "Pending Human Review",
        ),
        (
            "REC-003",
            "SRV-004",
            "ACT-003",
            "Escalate repeated critical breach remediation to the sponsor level",
            "A repeated critical SLO breach and customer impact require a stronger governance response.",
            "Evidence: SLO-EV-004-001 (verified critical breach recurring across "
            "three periods, 2026-11-02), FND-019, and linked overdue corrective actions.",
            "Service Manager",
            "President / Executive Sponsor, Delivery Assurance Leader",
            30,
            "2026-11-12",
            "Stabilize the service and remove uncontained critical-breach recurrence.",
            "Two consecutive reporting cycles complete without a repeated critical breach.",
            "High",
            "Penalty exposure may change if new customer evidence emerges; human review is mandatory.",
            "Pending Human Review",
        ),
    ]


def build_pilot_phases() -> list[tuple]:
    return [
        (
            "Days 1-30: Configure and Baseline",
            "1-30",
            "Delivery Assurance Leader",
            "Confirm personas, freeze synthetic baseline, configure rating rules, and validate ENG-007 and SRV-012 walkthrough data.",
            "Baseline evidence pack, owner list, first review cadence, and pilot dashboard sign-off.",
            "Baseline assumptions may be unclear if evidence owners do not confirm the sample set.",
            "Continue if both pilot engagements have accepted owners, baseline measures, and no unresolved data-definition dispute.",
        ),
        (
            "Days 31-60: Run and Refine",
            "31-60",
            "Engineering Manager / Service Manager",
            "Operate the review cycle, test AI recommendation review, and track 30/60-day actions with escalation where needed.",
            "Refined thresholds, approved actions, evidence refreshes, and sponsor-ready exception summaries.",
            "Teams may revert to manual reporting if the workflow feels heavier than the baseline process.",
            "Continue if governance preparation effort trends down and no control or service guardrail deteriorates without explanation.",
        ),
        (
            "Days 61-90: Verify and Decide",
            "61-90",
            "President / Executive Sponsor",
            "Verify closure evidence, compare pilot baselines to current results, and decide continue / revise / stop.",
            "Pilot outcome summary, verified evidence sample, rollout recommendation, and leadership decision record.",
            "Apparent improvement may not be reliable if closure evidence is owner-reported but not independently checked.",
            "Continue only if governance effort falls toward the 20% target, evidence traceability approaches 90%, and on-time verified action closure approaches 85% without degrading release failure or SLO performance.",
        ),
    ]


def derive_overall_status(observations: list[sqlite3.Row]) -> tuple[str, str]:
    red_dimensions = [
        row["dimension"]
        for row in observations
        if (row["performance_status"] == "Red" or row["critical_override"])
        and row["evidence_confidence"] == "Verified"
    ]
    if red_dimensions:
        label = DIMENSION_LABELS[red_dimensions[0]]
        return "Red", f"Verified Red override in {label}."

    unverified_red_dimensions = [
        row["dimension"]
        for row in observations
        if (row["performance_status"] == "Red" or row["critical_override"])
        and row["evidence_confidence"] != "Verified"
    ]
    amber_dimensions = [
        row["dimension"]
        for row in observations
        if row["performance_status"] == "Amber"
    ]
    if amber_dimensions:
        label = DIMENSION_LABELS[amber_dimensions[0]]
        if unverified_red_dimensions:
            return (
                "Amber",
                f"Amber follow-up in {label}; an unverified Red signal in "
                f"{DIMENSION_LABELS[unverified_red_dimensions[0]]} requires evidence review.",
            )
        return "Amber", f"Amber follow-up required in {label}."

    unknown_dimensions = [
        row["dimension"]
        for row in observations
        if row["performance_status"] == "Unknown"
        or row["evidence_confidence"] in {"Unknown", "Stale", "Unverified"}
    ]
    if unknown_dimensions or unverified_red_dimensions:
        dimension = (
            unknown_dimensions[0]
            if unknown_dimensions
            else unverified_red_dimensions[0]
        )
        label = DIMENSION_LABELS[dimension]
        return "Amber", f"Unknown evidence remains in {label}; treat as assurance follow-up, not poor performance."

    return "Green", "All dimensions are Green with no unresolved evidence gap."


class DemoRepository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connection(self) -> sqlite3.Connection:
        return create_connection(self.path)

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_portfolio_summary(self) -> dict[str, object]:
        with self.connection() as connection:
            status_counts = Counter(
                row["overall_status"]
                for row in connection.execute("SELECT overall_status FROM engagements")
            )
            findings_total = connection.execute(
                "SELECT COUNT(*) AS count FROM findings"
            ).fetchone()["count"]
            repeat_total = connection.execute(
                "SELECT COUNT(*) AS count FROM findings WHERE repeat_flag = 1"
            ).fetchone()["count"]
            action_total = connection.execute(
                "SELECT COUNT(*) AS count FROM actions"
            ).fetchone()["count"]
            overdue_total = connection.execute(
                """
                SELECT COUNT(*) AS count FROM actions
                WHERE due_date < ?
                  AND status NOT IN ('Completed', 'Owner Reported Complete', 'Verified', 'Rejected')
                """,
                (REFERENCE_DATE.isoformat(),),
            ).fetchone()["count"]
            release_total = connection.execute(
                "SELECT COUNT(*) AS count FROM releases"
            ).fetchone()["count"]
            traceable_total = connection.execute(
                "SELECT COUNT(*) AS count FROM releases WHERE traceable = 1"
            ).fetchone()["count"]
            engagement_total = connection.execute(
                "SELECT COUNT(*) AS count FROM engagements"
            ).fetchone()["count"]
            settings = {
                row["key"]: row["value"]
                for row in connection.execute(
                    "SELECT key, value FROM settings WHERE key = 'portfolio_baseline_hours'"
                )
            }
        return {
            "engagements": engagement_total,
            "red": status_counts["Red"],
            "amber": status_counts["Amber"],
            "green": status_counts["Green"],
            "repeat_findings": (
                f"{repeat_total}/{findings_total} "
                f"({format_percentage(repeat_total, findings_total)})"
            ),
            "overdue_actions": (
                f"{overdue_total}/{action_total} "
                f"({format_percentage(overdue_total, action_total)})"
            ),
            "traceable_releases": (
                f"{traceable_total}/{release_total} "
                f"({format_percentage(traceable_total, release_total)})"
            ),
            "governance_hours": int(
                settings.get("portfolio_baseline_hours", PORTFOLIO_BASELINE_HOURS)
            ),
        }

    def list_engagements(
        self, business_unit: str = "All", status: str = "All", search: str = ""
    ) -> list[sqlite3.Row]:
        query = """
            SELECT e.id, e.name, bu.name AS business_unit, e.engagement_type,
                   e.overall_status, e.overview_reason, e.accountable_lead
            FROM engagements e
            JOIN business_units bu ON bu.id = e.business_unit_id
            WHERE 1 = 1
        """
        params: list[str] = []
        if business_unit != "All":
            query += " AND bu.name = ?"
            params.append(business_unit)
        if status != "All":
            query += " AND e.overall_status = ?"
            params.append(status)
        if search.strip():
            query += " AND (e.id LIKE ? OR e.name LIKE ? OR e.engagement_type LIKE ?)"
            like = f"%{search.strip()}%"
            params.extend([like, like, like])
        query += " ORDER BY e.id"
        with self.connection() as connection:
            return list(connection.execute(query, params))

    def get_business_units(self) -> list[str]:
        with self.connection() as connection:
            return [row["name"] for row in connection.execute("SELECT name FROM business_units ORDER BY name")]

    def get_engagement(self, engagement_id: str) -> sqlite3.Row | None:
        with self.connection() as connection:
            return connection.execute(
                """
                SELECT e.*, bu.name AS business_unit
                FROM engagements e
                JOIN business_units bu ON bu.id = e.business_unit_id
                WHERE e.id = ?
                """,
                (engagement_id,),
            ).fetchone()

    def get_observations(self, engagement_id: str) -> list[sqlite3.Row]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    "SELECT * FROM observations WHERE engagement_id = ? ORDER BY sort_order",
                    (engagement_id,),
                )
            )

    def get_findings(self, engagement_id: str) -> list[sqlite3.Row]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    "SELECT * FROM findings WHERE engagement_id = ? ORDER BY opened_on DESC, id",
                    (engagement_id,),
                )
            )

    def get_releases(self, engagement_id: str) -> list[sqlite3.Row]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    "SELECT * FROM releases WHERE engagement_id = ? ORDER BY deployed_on DESC, id",
                    (engagement_id,),
                )
            )

    def get_service_events(self, engagement_id: str) -> list[sqlite3.Row]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT * FROM service_events
                    WHERE engagement_id = ?
                    ORDER BY evidence_date DESC, id
                    """,
                    (engagement_id,),
                )
            )

    def get_actions(self, engagement_id: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM actions"
        params: tuple[str, ...] = ()
        if engagement_id:
            query += " WHERE engagement_id = ?"
            params = (engagement_id,)
        query += " ORDER BY due_date, id"
        with self.connection() as connection:
            return list(connection.execute(query, params))

    def get_action_events(self, action_id: str) -> list[sqlite3.Row]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT * FROM action_events
                    WHERE action_id = ?
                    ORDER BY occurred_at DESC, id DESC
                    """,
                    (action_id,),
                )
            )

    def transition_action(
        self, action_id: str, new_status: str, actor_role: str, evidence: str = ""
    ) -> None:
        with self.connection() as connection:
            action = connection.execute(
                "SELECT * FROM actions WHERE id = ?", (action_id,)
            ).fetchone()
            if not action:
                raise ValueError(f"Action {action_id} was not found.")
            previous_status = action["status"]
            if new_status == "In Progress":
                allowed = previous_status == "Approved" and (
                    actor_role == action["accountable_owner"]
                )
                event_type = "Action started"
            elif new_status == "Owner Reported Complete":
                allowed = previous_status == "In Progress" and (
                    actor_role == action["accountable_owner"]
                )
                event_type = "Owner-reported completion"
                if not evidence.strip():
                    raise ValueError("Completion evidence is required.")
            elif new_status == "Verified":
                allowed = (
                    previous_status == "Owner Reported Complete"
                    and actor_role
                    in {
                        "Delivery Assurance Leader",
                        "Auditor / Control Reviewer",
                    }
                )
                event_type = "Effectiveness independently verified"
                if not evidence.strip():
                    raise ValueError("Independent verification evidence is required.")
            else:
                raise ValueError(f"Unsupported action transition: {new_status}")
            if not allowed:
                raise PermissionError(
                    f"{actor_role} cannot move action {action_id} from "
                    f"{previous_status} to {new_status}."
                )

            if new_status == "Owner Reported Complete":
                connection.execute(
                    """
                    UPDATE actions SET status = ?, completion_evidence = ?
                    WHERE id = ?
                    """,
                    (new_status, evidence.strip(), action_id),
                )
            elif new_status == "Verified":
                connection.execute(
                    """
                    UPDATE actions
                    SET status = ?, verified_effectiveness = ?
                    WHERE id = ?
                    """,
                    (new_status, evidence.strip(), action_id),
                )
            else:
                connection.execute(
                    "UPDATE actions SET status = ? WHERE id = ?",
                    (new_status, action_id),
                )
            connection.execute(
                """
                INSERT INTO action_events(
                    action_id, event_type, actor_role, previous_status,
                    new_status, evidence, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    event_type,
                    actor_role,
                    previous_status,
                    new_status,
                    evidence.strip(),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )

    def get_recommendations(self, engagement_id: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM recommendations"
        params: tuple[str, ...] = ()
        if engagement_id:
            query += " WHERE engagement_id = ?"
            params = (engagement_id,)
        query += " ORDER BY id"
        with self.connection() as connection:
            return list(connection.execute(query, params))

    def get_review_events(self, recommendation_id: str) -> list[sqlite3.Row]:
        with self.connection() as connection:
            return list(
                connection.execute(
                    """
                    SELECT * FROM review_events
                    WHERE recommendation_id = ?
                    ORDER BY occurred_at DESC, id DESC
                    """,
                    (recommendation_id,),
                )
            )

    def get_pilot_phases(self) -> list[sqlite3.Row]:
        with self.connection() as connection:
            return list(connection.execute("SELECT * FROM pilot_phases ORDER BY id"))

    def update_recommendation_state(
        self, recommendation_id: str, state: str, actor_role: str
    ) -> None:
        if not can_review_recommendations(actor_role):
            raise PermissionError("This role cannot review AI recommendations.")
        if state not in {"Approved", "Rejected", "Needs Edit"}:
            raise ValueError(f"Unsupported recommendation state: {state}")

        with self.connection() as connection:
            recommendation = connection.execute(
                "SELECT * FROM recommendations WHERE id = ?",
                (recommendation_id,),
            ).fetchone()
            if not recommendation:
                raise ValueError(f"Recommendation {recommendation_id} was not found.")
            previous_state = recommendation["state"]
            if previous_state not in {"Pending Human Review", "Needs Edit"}:
                raise ValueError(
                    f"Recommendation {recommendation_id} is already {previous_state}."
                )
            if previous_state == state:
                raise ValueError(
                    f"Recommendation {recommendation_id} is already {state}."
                )

            linked_action_id = recommendation["linked_action_id"]
            if state == "Approved":
                if not linked_action_id:
                    raise ValueError(
                        "Approval requires a linked action with one accountable owner."
                    )
                action = connection.execute(
                    "SELECT * FROM actions WHERE id = ?",
                    (linked_action_id,),
                ).fetchone()
                if not action or action["status"] != "Draft":
                    raise ValueError(
                        "Only an unassigned Draft action can be activated by approval."
                    )
                if recommendation["proposed_owner"] not in ROLE_CAPABILITIES:
                    raise ValueError(
                        "The linked action owner is not in the approved role list."
                    )
                connection.execute(
                    """
                    UPDATE actions
                    SET title = ?, accountable_owner = ?, contributors = ?,
                        horizon_days = ?, due_date = ?, expected_outcome = ?,
                        success_measure = ?, status = 'Approved'
                    WHERE id = ?
                    """,
                    (
                        recommendation["title"],
                        recommendation["proposed_owner"],
                        recommendation["contributors"],
                        recommendation["horizon_days"],
                        recommendation["due_date"],
                        recommendation["expected_outcome"],
                        recommendation["success_measure"],
                        linked_action_id,
                    ),
                )
            elif state == "Rejected" and linked_action_id:
                connection.execute(
                    "UPDATE actions SET status = 'Rejected' WHERE id = ? AND status = 'Draft'",
                    (linked_action_id,),
                )

            connection.execute(
                "UPDATE recommendations SET state = ? WHERE id = ?",
                (state, recommendation_id),
            )
            if linked_action_id and state in {"Approved", "Rejected"}:
                action = connection.execute(
                    "SELECT status FROM actions WHERE id = ?",
                    (linked_action_id,),
                ).fetchone()
                if action and action["status"] == state:
                    connection.execute(
                        """
                        INSERT INTO action_events(
                            action_id, event_type, actor_role, previous_status,
                            new_status, evidence, occurred_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            linked_action_id,
                            "Human approval" if state == "Approved" else "Human rejection",
                            actor_role,
                            "Draft",
                            state,
                            f"Recommendation {recommendation_id}",
                            datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        ),
                    )
            connection.execute(
                """
                INSERT INTO review_events(
                    recommendation_id, event_type, actor_role, previous_state,
                    new_state, details, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation_id,
                    "State changed",
                    actor_role,
                    previous_state,
                    state,
                    json.dumps({"linked_action_id": linked_action_id}),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )

    def update_recommendation_details(
        self,
        recommendation_id: str,
        fields: dict[str, str | int],
        actor_role: str,
    ) -> None:
        if not can_review_recommendations(actor_role):
            raise PermissionError("This role cannot edit AI recommendations.")
        required_text = ("title", "proposed_owner", "due_date", "expected_outcome", "success_measure")
        for field in required_text:
            if not str(fields.get(field, "")).strip():
                raise ValueError(f"{field.replace('_', ' ').title()} is required.")
        if fields["proposed_owner"] not in ROLE_CAPABILITIES:
            raise ValueError("Choose one accountable owner from the approved role list.")
        if fields.get("horizon_days") not in {30, 60, 90}:
            raise ValueError("The action horizon must be 30, 60, or 90 days.")
        try:
            date.fromisoformat(str(fields["due_date"]))
        except ValueError as error:
            raise ValueError("Due date must use YYYY-MM-DD format.") from error

        with self.connection() as connection:
            recommendation = connection.execute(
                "SELECT * FROM recommendations WHERE id = ?",
                (recommendation_id,),
            ).fetchone()
            if not recommendation:
                raise ValueError(f"Recommendation {recommendation_id} was not found.")
            if recommendation["state"] not in {
                "Pending Human Review",
                "Needs Edit",
            }:
                raise ValueError(
                    "Only pending or returned recommendations can be edited."
                )
            linked_action_id = recommendation["linked_action_id"]
            action = connection.execute(
                "SELECT * FROM actions WHERE id = ?",
                (linked_action_id,),
            ).fetchone() if linked_action_id else None
            if not action or action["status"] != "Draft":
                raise ValueError("Only a linked Draft action can be edited.")

            updated = {
                "title": str(fields["title"]).strip(),
                "proposed_owner": str(fields["proposed_owner"]),
                "contributors": str(fields.get("contributors", "")).strip(),
                "horizon_days": int(fields["horizon_days"]),
                "due_date": str(fields["due_date"]),
                "expected_outcome": str(fields["expected_outcome"]).strip(),
                "success_measure": str(fields["success_measure"]).strip(),
            }
            before = {
                key: recommendation[key]
                for key in updated
            }
            connection.execute(
                """
                UPDATE recommendations
                SET title = ?, proposed_owner = ?, contributors = ?,
                    horizon_days = ?, due_date = ?, expected_outcome = ?,
                    success_measure = ?
                WHERE id = ?
                """,
                (
                    updated["title"],
                    updated["proposed_owner"],
                    updated["contributors"],
                    updated["horizon_days"],
                    updated["due_date"],
                    updated["expected_outcome"],
                    updated["success_measure"],
                    recommendation_id,
                ),
            )
            connection.execute(
                """
                UPDATE actions
                SET title = ?, accountable_owner = ?, contributors = ?,
                    horizon_days = ?, due_date = ?, expected_outcome = ?,
                    success_measure = ?
                WHERE id = ?
                """,
                (
                    updated["title"],
                    updated["proposed_owner"],
                    updated["contributors"],
                    updated["horizon_days"],
                    updated["due_date"],
                    updated["expected_outcome"],
                    updated["success_measure"],
                    linked_action_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO review_events(
                    recommendation_id, event_type, actor_role, previous_state,
                    new_state, details, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recommendation_id,
                    "Proposal edited",
                    actor_role,
                    recommendation["state"],
                    recommendation["state"],
                    json.dumps({"before": before, "after": updated}),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )

    def build_decision_brief(self) -> str:
        summary = self.get_portfolio_summary()
        eng7 = self.get_engagement("ENG-007")
        srv12 = self.get_engagement("SRV-012")
        dimension_counts: dict[str, Counter[str]] = {
            dimension: Counter() for dimension in DIMENSIONS
        }
        with self.connection() as connection:
            for observation in connection.execute(
                "SELECT dimension, performance_status FROM observations"
            ):
                dimension_counts[observation["dimension"]][
                    observation["performance_status"]
                ] += 1
        engagement_basis = self.list_engagements()
        lines = [
            "Engineering & Service Assurance Decision Brief",
            "",
            "Contest alignment",
            "- Synthetic data only.",
            "- Preserves supplied portfolio facts: 28 engagements, 4 Red, 9 Amber, 15 Green, 22% repeat findings, 31% overdue actions, 64% traceable release evidence, and 240 governance person-hours per month.",
            "- Unknown evidence is shown as Unknown and treated as an assurance follow-up, not automatic poor performance.",
            "",
            "PS03 leadership summary",
            "The portfolio view preserves the supplied 4/9/15 health mix while surfacing a verified release-quality risk at ENG-007 and an evidence-control gap at SRV-012. Approve named owners and a two-engagement, 90-day pilot; scale only if evidence quality, action verification, and service guardrails hold.",
            "",
            "Portfolio view",
            "- Scope: 28 engagements across five synthetic business units.",
            f"- Portfolio health mix: {summary['red']} Red / {summary['amber']} Amber / {summary['green']} Green.",
            f"- Repeat findings: {summary['repeat_findings']}.",
            f"- Overdue actions: {summary['overdue_actions']}.",
            f"- Release evidence traceability: {summary['traceable_releases']}.",
            f"- Governance baseline: {summary['governance_hours']} person-hours per month.",
            "- Synthetic denominator choices: 11/50 repeat findings, 9/29 overdue actions, and 16/25 traceable sampled releases.",
            "",
            "Health by dimension (engagement counts; Unknown is separate)",
            *[
                f"- {DIMENSION_LABELS[dimension]}: "
                f"{dimension_counts[dimension]['Red']} Red / "
                f"{dimension_counts[dimension]['Amber']} Amber / "
                f"{dimension_counts[dimension]['Green']} Green / "
                f"{dimension_counts[dimension]['Unknown']} Unknown."
                for dimension in DIMENSIONS
            ],
            "",
            "Overall engagement rating basis",
            *[
                f"- {row['id']} | {row['overall_status']} | {row['overview_reason']}"
                for row in engagement_basis
            ],
            "",
            "Rating assumptions",
            *[f"- {assumption}" for assumption in RATING_ASSUMPTIONS],
            "",
            "Leadership decisions required",
            "- Confirm that verified Red quality or service signals override superficially healthy milestone reporting.",
            "- Approve one accountable owner per action and enforce 30/60/90-day checkpoints.",
            "- Separate evidence quality problems from actual performance decline so interventions stay fair.",
            "- Use a small, explainable six-dimension scorecard instead of opaque averaging.",
            "",
            "Illustrative engagement: ENG-007",
            f"- {eng7['executive_summary']}",
            "- Delivery predictability: Green at 97%.",
            "- Release quality: Red at 25% failed or rolled-back production releases with verified defect leakage.",
            "- Overall: Red because verified quality risk cannot be masked by milestone performance.",
            "",
            "Illustrative engagement: SRV-012",
            f"- {srv12['executive_summary']}",
            "- Service stability: Green at 99% SLO compliance with no material breach or penalty.",
            "- Evidence traceability: Amber at 64% (16 of 25 synthetic sampled releases fully traceable).",
            "- Overall: Amber because the evidence-control gap is verified even though service performance is stable.",
            "",
            "Priority interventions",
            "- ENG-007: Engineering Manager owns release-risk containment by 2026-11-18; do not allow healthy milestones to override the verified 25% release-failure signal.",
            "- SRV-012: Service Manager owns traceability correction by 2026-12-12; maintain Green service stability while repairing the evidence-control gap.",
            "- SRV-004: Service Manager owns immediate escalation for the verified repeated critical SLO breach and estimated penalty exposure.",
            "- Reduce governance effort by standardizing evidence capture and AI-assisted recommendation review with mandatory human approval.",
            "",
            "SLO and penalty evidence",
            "- SRV-004 includes a synthetic verified critical SLO breach recurring across three periods, with 12,000 illustrative penalty units estimated and none assessed.",
            "- Penalty units are fictional demonstration values, not real pricing or contract exposure.",
            "",
            "Application walkthrough for the integrated three-minute summary",
            "- Portfolio dashboard -> ENG-007 detail -> SRV-012 detail -> AI recommendation review -> 30/60/90-day action view.",
        ]
        return "\n".join(lines)

    def build_pilot_plan(self) -> str:
        phases = self.get_pilot_phases()
        lines = [
            "Governance Improvement & 90-Day Pilot Plan",
            "",
            "Workflow and safeguards",
            "- Engineering and Service Managers refresh evidence; data-quality checks flag missing, stale, and conflicting inputs before scoring.",
            "- Approved deterministic rules calculate dimension status; Delivery Assurance reviews the result and AI does not set official ratings.",
            "- Recommendations cite evidence IDs and dates, separate facts from hypotheses, disclose uncertainty, and remain pending until a sponsor or Delivery Assurance Leader approves, edits, or rejects them.",
            "- Action states: Draft → Approved → In Progress → Owner Reported Complete → Verified. The named owner reports completion; an Auditor / Control Reviewer or Delivery Assurance Leader independently verifies effectiveness.",
            "- Every accepted action keeps one accountable owner, optional contributors, a due date, a 30/60/90-day horizon, expected outcome, success measure, escalation condition, and completion evidence.",
            "- Escalate immediately for a verified critical customer-impacting release incident or critical SLO breach; raise other risks at the next owner/review checkpoint.",
            "- The Executive Sponsor resolves portfolio trade-offs and Day 90 continue / revise / stop; auditors can flag evidence or closure gaps.",
            "",
            "90-day pilot",
        ]
        for phase in phases:
            lines.extend(
                [
                    f"- {phase['phase_name']}",
                    f"  Owner: {phase['owner']}",
                    f"  Checkpoints: {phase['checkpoints']}",
                    f"  Expected outputs: {phase['expected_outputs']}",
                    f"  Risks: {phase['risks']}",
                    f"  Decision criteria: {phase['decision_criteria']}",
                ]
            )
        lines.extend(
            [
                "",
                "Illustrative pilot measures and assumptions",
                "- Governance preparation effort: measure a pilot-specific Day 0 baseline; proposed target is a 20% reduction by Day 90.",
                "- Evidence traceability: measure a pilot-specific baseline; proposed target is at least 90% of sampled releases fully traceable by Day 90.",
                "- Actions closed on time and verified: measure a pilot-specific baseline; proposed target is at least 85% of actions due in the pilot.",
                "- Operational guardrail: release failure rate and SLO compliance must not deteriorate without explanation and escalation.",
                "- The portfolio figures of 240 governance hours/month, 64% traceability, 31% overdue actions, and 22% repeat findings are context—not pilot baselines or proof of pilot impact.",
                "",
                "Day 90 decision",
                "- Continue if the pilot shows lower governance effort, stronger evidence traceability, and verified action closure without degrading release or service outcomes.",
                "- Revise if the workflow is valuable but thresholds, ownership, or evidence collection still create friction.",
                "- Stop if the pilot increases effort, obscures accountability, or fails to preserve assurance quality.",
            ]
        )
        return "\n".join(lines)

    def export_decision_pack(self) -> list[Path]:
        EXPORT_DIR.mkdir(exist_ok=True)
        brief_path = EXPORT_DIR / "03_D1_Engineering_and_Service_Assurance_Decision_Brief.txt"
        plan_path = EXPORT_DIR / "03_D2_Governance_Improvement_and_90_Day_Pilot_Plan.txt"
        brief_path.write_text(self.build_decision_brief(), encoding="utf-8")
        plan_path.write_text(self.build_pilot_plan(), encoding="utf-8")
        return [brief_path, plan_path]


def validate_dataset(repo: DemoRepository) -> list[str]:
    issues: list[str] = []
    summary = repo.get_portfolio_summary()
    expected = {
        "engagements": 28,
        "red": 4,
        "amber": 9,
        "green": 15,
        "repeat_findings": "11/50 (22%)",
        "overdue_actions": "9/29 (31%)",
        "traceable_releases": "16/25 (64%)",
        "governance_hours": 240,
    }
    for key, value in expected.items():
        if summary[key] != value:
            issues.append(f"Expected {key} = {value}, found {summary[key]}")

    if len(repo.get_business_units()) != 5:
        issues.append("Expected exactly five synthetic business units.")
    if sum(summary[key] for key in ("red", "amber", "green")) != summary["engagements"]:
        issues.append("Portfolio health counts do not reconcile to engagement count.")

    engagements = repo.list_engagements()
    for row in engagements:
        observations = repo.get_observations(row["id"])
        observed_dimensions = {item["dimension"] for item in observations}
        if observed_dimensions != set(DIMENSIONS) or len(observations) != len(DIMENSIONS):
            issues.append(
                f"{row['id']} must have exactly one observation for each of the six dimensions."
            )
        derived_status, reason = derive_overall_status(observations)
        if derived_status != row["overall_status"]:
            issues.append(
                f"{row['id']} stored {row['overall_status']} but derives {derived_status}: {reason}"
            )
        for item in observations:
            if item["performance_status"] not in {"Red", "Amber", "Green", "Unknown"}:
                issues.append(
                    f"{row['id']} has invalid status {item['performance_status']}."
                )
            if (
                item["evidence_confidence"] in {"Unknown", "Stale", "Unverified"}
                and item["performance_status"] != "Unknown"
            ):
                issues.append(
                    f"{row['id']} treats missing or stale {item['dimension']} evidence as performance."
                )
            if not item["evidence_ref"] or not item["evidence_date"]:
                issues.append(
                    f"{row['id']} {item['dimension']} is missing its evidence source or as-of date."
                )

    for engagement_id, expected_status in {"ENG-007": "Red", "SRV-012": "Amber"}.items():
        engagement = repo.get_engagement(engagement_id)
        observations = repo.get_observations(engagement_id)
        derived_status, reason = derive_overall_status(observations)
        if not engagement or engagement["overall_status"] != expected_status:
            issues.append(f"Engagement {engagement_id} overall status mismatch.")
        if derived_status != expected_status:
            issues.append(f"Derived status for {engagement_id} expected {expected_status}, found {derived_status} ({reason})")

    eng7 = {row["dimension"]: row["performance_status"] for row in repo.get_observations("ENG-007")}
    srv12 = {row["dimension"]: row["performance_status"] for row in repo.get_observations("SRV-012")}
    if eng7.get("delivery_predictability") != "Green":
        issues.append("ENG-007 delivery predictability should be Green.")
    if eng7.get("release_quality") != "Red":
        issues.append("ENG-007 release quality should be Red.")
    if srv12.get("service_stability") != "Green":
        issues.append("SRV-012 service stability should be Green.")
    if srv12.get("evidence_traceability") != "Amber":
        issues.append("SRV-012 evidence traceability should be Amber.")

    boundaries = [
        (rate_delivery_predictability(None), "Unknown"),
        (rate_delivery_predictability(95), "Amber"),
        (rate_delivery_predictability(95.01), "Green"),
        (rate_delivery_predictability(80), "Amber"),
        (rate_delivery_predictability(79.99), "Red"),
        (rate_evidence_traceability(95), "Amber"),
        (rate_evidence_traceability(95.01), "Green"),
        (rate_evidence_traceability(60), "Amber"),
        (rate_evidence_traceability(59.99), "Red"),
        (rate_release_failure(10), "Green"),
        (rate_release_failure(10.01), "Amber"),
        (rate_release_failure(20), "Amber"),
        (rate_release_failure(20.01), "Red"),
        (rate_release_failure(8, verified_severity_1_incident=True), "Red"),
        (rate_slo_compliance(95), "Amber"),
        (rate_slo_compliance(95.01), "Green"),
        (rate_slo_compliance(99, verified=False), "Unknown"),
        (
            rate_service_stability(99, "Critical", 1, 0),
            "Red",
        ),
        (
            rate_service_stability(99, "Noncritical", 1, 0),
            "Amber",
        ),
        (rate_service_stability(99, None, 0, 100), "Red"),
        (rate_repeat_findings(10), "Amber"),
        (rate_repeat_findings(25), "Amber"),
        (rate_repeat_findings(25.01), "Red"),
        (rate_overdue_actions(15), "Green"),
        (rate_overdue_actions(15.01), "Amber"),
        (rate_overdue_actions(40), "Amber"),
        (rate_overdue_actions(40.01), "Red"),
    ]
    for actual, expected_status in boundaries:
        if actual != expected_status:
            issues.append(
                f"Rating boundary expected {expected_status}, found {actual}."
            )

    with repo.connection() as connection:
        actions = list(connection.execute("SELECT * FROM actions"))
        findings = {
            row["id"]
            for row in connection.execute("SELECT id FROM findings")
        }
        recommendations = list(
            connection.execute("SELECT * FROM recommendations")
        )
        service_events = list(
            connection.execute("SELECT * FROM service_events")
        )
    if len(actions) != 29:
        issues.append(f"Expected 29 synthetic actions, found {len(actions)}.")
    for action in actions:
        if action["accountable_owner"] not in ROLE_CAPABILITIES:
            issues.append(f"{action['id']} must have exactly one approved role owner.")
        if action["horizon_days"] not in {30, 60, 90}:
            issues.append(f"{action['id']} has an unsupported action horizon.")
        if action["trigger_ref"] not in findings:
            issues.append(f"{action['id']} trigger {action['trigger_ref']} is not linked to a finding.")
        if not action["expected_outcome"] or not action["completion_evidence"]:
            issues.append(f"{action['id']} is missing outcome or completion evidence.")
        if (
            action["status"] == "Owner Reported Complete"
            and action["completion_evidence"] == "Awaiting independent verification"
        ):
            issues.append(
                f"{action['id']} is owner-reported complete without completion evidence."
            )
        if (
            action["status"] == "Verified"
            and action["verified_effectiveness"]
            in {"", "Verified", "Pending independent verification"}
        ):
            issues.append(
                f"{action['id']} is Verified without independent effectiveness evidence."
            )
    for recommendation in recommendations:
        if recommendation["proposed_owner"] not in ROLE_CAPABILITIES:
            issues.append(
                f"{recommendation['id']} owner is outside the approved role list."
            )
        if recommendation["horizon_days"] not in {30, 60, 90}:
            issues.append(f"{recommendation['id']} has an unsupported horizon.")
        if not recommendation["evidence_summary"] or not recommendation["uncertainty"]:
            issues.append(
                f"{recommendation['id']} must cite evidence and disclose uncertainty."
            )
        if recommendation["state"] == "Pending Human Review":
            action = next(
                (
                    item
                    for item in actions
                    if item["id"] == recommendation["linked_action_id"]
                ),
                None,
            )
            if not action or action["status"] != "Draft":
                issues.append(
                    f"{recommendation['id']} must not activate its action before human approval."
                )
    if not any(
        event["engagement_id"] == "SRV-004"
        and event["severity"] == "Critical"
        and event["recurrence_count"] > 1
        and event["verified"]
        and event["estimated_penalty_units"] > 0
        for event in service_events
    ):
        issues.append(
            "Synthetic data must include a verified repeated critical SLO event with estimated penalty exposure."
        )
    expected_service_status = {
        "SRV-004": "Red",
        "SRV-007": "Amber",
        "SRV-009": "Red",
        "SRV-012": "Green",
    }
    for engagement_id, expected_status in expected_service_status.items():
        event = next(
            (
                item
                for item in service_events
                if item["engagement_id"] == engagement_id
                and (
                    engagement_id != "SRV-009"
                    or item["severity"] == "Critical"
                )
            ),
            None,
        )
        observation = next(
            (
                item
                for item in repo.get_observations(engagement_id)
                if item["dimension"] == "service_stability"
            ),
            None,
        )
        if not event or not observation or not observation["denominator"]:
            issues.append(
                f"{engagement_id} is missing the SLO evidence needed to validate service stability."
            )
            continue
        compliance = 100 * observation["numerator"] / observation["denominator"]
        event_severity = (
            None if event["severity"] == "None" else event["severity"]
        )
        calculated_status = rate_service_stability(
            compliance,
            event_severity,
            event["recurrence_count"],
            event["assessed_penalty_units"],
            evidence_verified=bool(event["verified"]),
        )
        if calculated_status != expected_status:
            issues.append(
                f"{engagement_id} service stability expected {expected_status}, "
                f"calculated {calculated_status}."
            )
    if not can_review_recommendations("Delivery Assurance Leader") or can_review_recommendations("Service Manager"):
        issues.append("Recommendation review role permissions are inconsistent.")

    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        unverified_red = connection.execute(
            """
            SELECT 'delivery_predictability' AS dimension,
                   'Red' AS performance_status,
                   'Partial' AS evidence_confidence,
                   0 AS critical_override
            """
        ).fetchone()
        derived_status, _ = derive_overall_status([unverified_red])
        if derived_status == "Red":
            issues.append("An unverified Red signal must not create an overall Red.")

    return issues


def run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--reset-db", action="store_true", help="Rebuild the synthetic SQLite database")
    parser.add_argument("--validate", action="store_true", help="Run dataset validation checks without launching the UI")
    parser.add_argument("--export-pack", action="store_true", help="Export the two PS03 contest outputs as text files")
    args = parser.parse_args(argv)

    seed_database(reset=args.reset_db, path=DB_PATH)
    repo = DemoRepository(DB_PATH)

    if args.validate:
        issues = validate_dataset(repo)
        if issues:
            for item in issues:
                print(f"VALIDATION ERROR: {item}")
            return 1
        print("Validation passed: portfolio facts, exemplar engagements, and deliverable baselines reconcile.")
        return 0

    if args.export_pack:
        for path in repo.export_decision_pack():
            print(path)
        return 0

    return launch_gui(repo)


def launch_gui(repo: DemoRepository) -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QAction
        from PySide6.QtWidgets import (
            QApplication,
            QComboBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QInputDialog,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QPlainTextEdit,
            QScrollArea,
            QSizePolicy,
            QSplitter,
            QTabWidget,
            QTableWidget,
            QTableWidgetItem,
            QTextBrowser,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is not installed. Install dependencies with: python -m pip install -r requirements.txt")
        return 1

    class MainWindow(QMainWindow):
        def __init__(self, repository: DemoRepository) -> None:
            super().__init__()
            self.repo = repository
            self.current_engagement_id = "ENG-007"
            self.current_action_id: str | None = None
            self.setWindowTitle(f"{APP_TITLE} | Executive Portfolio")
            self.resize(1600, 960)

            self._build_ui()
            self.refresh_all()

        def _build_ui(self) -> None:
            container = QWidget()
            container.setObjectName("mainContainer")
            main_layout = QVBoxLayout(container)
            main_layout.setContentsMargins(20, 18, 20, 18)
            main_layout.setSpacing(14)

            header = QWidget()
            header.setObjectName("executiveHeader")
            header_layout = QVBoxLayout(header)
            header_layout.setContentsMargins(20, 15, 20, 16)
            header_layout.setSpacing(4)

            eyebrow = QLabel("EXECUTIVE ASSURANCE WORKSPACE")
            eyebrow.setObjectName("headerEyebrow")
            title = QLabel("PS03 Assurance Studio")
            title.setObjectName("headerTitle")

            subtitle = QLabel(
                "Software Quality, Engagement Health & Delivery Assurance  |  "
                "Synthetic demonstration data"
            )
            subtitle.setWordWrap(True)
            subtitle.setObjectName("headerSubtitle")
            header_layout.addWidget(eyebrow)
            header_layout.addWidget(title)
            header_layout.addWidget(subtitle)

            control_row = QHBoxLayout()
            control_row.setSpacing(10)
            self.role_combo = QComboBox()
            self.role_combo.addItems(list(ROLE_CAPABILITIES))
            self.role_combo.setCurrentText(self.repo.get_setting("current_role", list(ROLE_CAPABILITIES)[1]))
            self.role_combo.currentTextChanged.connect(self.on_role_changed)

            self.provider_combo = QComboBox()
            self.provider_combo.addItems(AI_PROVIDERS)
            self.provider_combo.setCurrentText(self.repo.get_setting("ai_provider", AI_PROVIDERS[0]))
            self.provider_combo.currentTextChanged.connect(self.on_provider_changed)

            export_button = QPushButton("Export PS03 outputs")
            export_button.clicked.connect(self.export_pack)

            validate_button = QPushButton("Run validation")
            validate_button.clicked.connect(self.run_validation_dialog)

            control_row.addWidget(QLabel("Role view"))
            control_row.addWidget(self.role_combo)
            control_row.addWidget(QLabel("Provider preference · demo only"))
            control_row.addWidget(self.provider_combo)
            control_row.addStretch(1)
            control_row.addWidget(export_button)
            control_row.addWidget(validate_button)

            self.role_card = QLabel()
            self.role_card.setWordWrap(True)
            self.role_card.setObjectName("roleNotice")

            self.tabs = QTabWidget()
            self.tabs.addTab(self._build_portfolio_tab(), "Executive Portfolio")
            self.tabs.addTab(self._build_detail_tab(), "Engagement Detail")
            self.tabs.addTab(self._build_evidence_tab(), "Evidence & Findings")
            self.tabs.addTab(self._build_ai_tab(), "AI Recommendation Review")
            self.tabs.addTab(self._build_actions_tab(), "30/60/90-Day Actions & Pilot")

            main_layout.addWidget(header)
            main_layout.addLayout(control_row)
            main_layout.addWidget(self.role_card)
            main_layout.addWidget(self.tabs)
            self.setCentralWidget(container)

            file_menu = self.menuBar().addMenu("File")
            export_action = QAction("Export PS03 outputs", self)
            export_action.triggered.connect(self.export_pack)
            file_menu.addAction(export_action)

        def _build_portfolio_tab(self) -> QWidget:
            tab = QWidget()
            layout = QVBoxLayout(tab)

            self.portfolio_dashboard = QTextBrowser()
            self.portfolio_dashboard.setObjectName("portfolioDashboard")
            self.portfolio_dashboard.setOpenLinks(False)
            self.portfolio_dashboard.setMaximumHeight(228)
            self.portfolio_dashboard.setAccessibleName(
                "Executive portfolio snapshot with health mix and assurance indicators"
            )

            filters = QHBoxLayout()
            self.bu_filter = QComboBox()
            self.bu_filter.addItems(["All", *self.repo.get_business_units()])
            self.bu_filter.currentTextChanged.connect(self.refresh_portfolio_table)

            self.status_filter = QComboBox()
            self.status_filter.addItems(["All", "Red", "Amber", "Green"])
            self.status_filter.currentTextChanged.connect(self.refresh_portfolio_table)

            self.search_filter = QLineEdit()
            self.search_filter.setPlaceholderText("Search engagement id, name, or type")
            self.search_filter.textChanged.connect(self.refresh_portfolio_table)

            filters.addWidget(QLabel("Business unit"))
            filters.addWidget(self.bu_filter)
            filters.addWidget(QLabel("Status"))
            filters.addWidget(self.status_filter)
            filters.addWidget(QLabel("Search"))
            filters.addWidget(self.search_filter)

            splitter = QSplitter(Qt.Orientation.Horizontal)

            self.engagement_table = QTableWidget(0, 6)
            self.engagement_table.setHorizontalHeaderLabels(
                ["ID", "Engagement", "Business Unit", "Type", "Status", "Accountable Lead"]
            )
            self.engagement_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.engagement_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.engagement_table.itemSelectionChanged.connect(self.on_engagement_selected)
            self.engagement_table.horizontalHeader().setStretchLastSection(True)
            splitter.addWidget(self.engagement_table)

            right_panel = QWidget()
            right_layout = QVBoxLayout(right_panel)
            self.leadership_summary = QPlainTextEdit()
            self.leadership_summary.setReadOnly(True)
            self.leadership_summary.setPlaceholderText("Leadership summary")
            self.deliverable_summary = QPlainTextEdit()
            self.deliverable_summary.setReadOnly(True)
            self.deliverable_summary.setPlaceholderText("Deliverable summary")
            right_layout.addWidget(QLabel("Leadership summary for the selected engagement"))
            right_layout.addWidget(self.leadership_summary)
            right_layout.addWidget(QLabel("PS03 deliverable focus"))
            right_layout.addWidget(self.deliverable_summary)
            splitter.addWidget(right_panel)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 2)

            layout.addWidget(self.portfolio_dashboard)
            layout.addLayout(filters)
            layout.addWidget(splitter)
            return tab

        def _build_detail_tab(self) -> QWidget:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            self.detail_header = QLabel()
            self.detail_header.setStyleSheet("font-size: 20px; font-weight: 700;")
            self.detail_context = QLabel()
            self.detail_context.setWordWrap(True)
            self.detail_context.setStyleSheet("color: #475569;")

            self.dimension_table = QTableWidget(0, 8)
            self.dimension_table.setHorizontalHeaderLabels(
                [
                    "Dimension",
                    "Measure",
                    "Value",
                    "Status",
                    "Evidence confidence",
                    "Source reference",
                    "Evidence date",
                    "Explanation",
                ]
            )
            self.dimension_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.dimension_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.dimension_table.horizontalHeader().setStretchLastSection(True)

            self.decision_logic = QPlainTextEdit()
            self.decision_logic.setReadOnly(True)

            layout.addWidget(self.detail_header)
            layout.addWidget(self.detail_context)
            layout.addWidget(self.dimension_table)
            layout.addWidget(QLabel("Explainable roll-up logic for the selected engagement"))
            layout.addWidget(self.decision_logic)
            return tab

        def _build_evidence_tab(self) -> QWidget:
            tab = QWidget()
            layout = QVBoxLayout(tab)
            splitter = QSplitter(Qt.Orientation.Vertical)

            findings_widget = QWidget()
            findings_layout = QVBoxLayout(findings_widget)
            self.findings_table = QTableWidget(0, 7)
            self.findings_table.setHorizontalHeaderLabels(
                ["Finding", "Category", "Severity", "Status", "Repeat", "Evidence", "Opened"]
            )
            self.findings_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.findings_table.horizontalHeader().setStretchLastSection(True)
            findings_layout.addWidget(QLabel("Findings and control observations"))
            findings_layout.addWidget(self.findings_table)

            releases_widget = QWidget()
            releases_layout = QVBoxLayout(releases_widget)
            self.releases_table = QTableWidget(0, 6)
            self.releases_table.setHorizontalHeaderLabels(
                ["Release", "Deployed", "Traceable", "Failure rate", "Verified incident", "Evidence"]
            )
            self.releases_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.releases_table.horizontalHeader().setStretchLastSection(True)
            releases_layout.addWidget(QLabel("Release samples and evidence traceability"))
            releases_layout.addWidget(self.releases_table)

            service_widget = QWidget()
            service_layout = QVBoxLayout(service_widget)
            self.service_events_table = QTableWidget(0, 8)
            self.service_events_table.setHorizontalHeaderLabels(
                [
                    "SLO event",
                    "Objective",
                    "Severity / repeats",
                    "Customer impact",
                    "Assessed penalty units",
                    "Estimated penalty units",
                    "Evidence",
                    "Verification",
                ]
            )
            self.service_events_table.setEditTriggers(
                QTableWidget.EditTrigger.NoEditTriggers
            )
            self.service_events_table.horizontalHeader().setStretchLastSection(True)
            service_layout.addWidget(
                QLabel(
                    "SLO breaches and illustrative penalty exposure "
                    "(synthetic units; not contract values)"
                )
            )
            service_layout.addWidget(self.service_events_table)

            splitter.addWidget(findings_widget)
            splitter.addWidget(releases_widget)
            splitter.addWidget(service_widget)
            splitter.setSizes([280, 280, 220])
            layout.addWidget(splitter)
            return tab

        def _build_ai_tab(self) -> QWidget:
            tab = QWidget()
            layout = QVBoxLayout(tab)

            self.ai_guardrail = QLabel(
                "AI may explain evidence-backed patterns and propose actions. It cannot change official ratings, assign actions without human approval, or invent facts."
            )
            self.ai_guardrail.setWordWrap(True)
            self.ai_guardrail.setObjectName("roleNotice")
            layout.addWidget(self.ai_guardrail)

            splitter = QSplitter(Qt.Orientation.Horizontal)
            self.recommendation_table = QTableWidget(0, 6)
            self.recommendation_table.setHorizontalHeaderLabels(
                ["Recommendation", "Engagement", "Owner", "Horizon", "Confidence", "State"]
            )
            self.recommendation_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.recommendation_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.recommendation_table.itemSelectionChanged.connect(self.on_recommendation_selected)
            self.recommendation_table.horizontalHeader().setStretchLastSection(True)
            splitter.addWidget(self.recommendation_table)

            detail_panel = QWidget()
            detail_layout = QVBoxLayout(detail_panel)
            self.recommendation_detail = QTextEdit()
            self.recommendation_detail.setReadOnly(True)
            self.recommendation_detail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            detail_layout.addWidget(self.recommendation_detail)

            button_row = QHBoxLayout()
            self.approve_button = QPushButton("Approve action")
            self.approve_button.clicked.connect(lambda: self.change_recommendation_state("Approved"))
            self.edit_button = QPushButton("Edit proposal")
            self.edit_button.clicked.connect(self.edit_recommendation)
            self.return_button = QPushButton("Return for revision")
            self.return_button.clicked.connect(
                lambda: self.change_recommendation_state("Needs Edit")
            )
            self.reject_button = QPushButton("Reject")
            self.reject_button.clicked.connect(lambda: self.change_recommendation_state("Rejected"))
            button_row.addWidget(self.edit_button)
            button_row.addWidget(self.return_button)
            button_row.addWidget(self.approve_button)
            button_row.addWidget(self.reject_button)
            button_row.addStretch(1)
            detail_layout.addLayout(button_row)

            splitter.addWidget(detail_panel)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 2)
            layout.addWidget(splitter)

            layout.addWidget(QLabel("Recommendation review audit trail"))
            self.review_events_table = QTableWidget(0, 5)
            self.review_events_table.setHorizontalHeaderLabels(
                ["Occurred (UTC)", "Event", "Reviewer role", "Previous state", "New state"]
            )
            self.review_events_table.setEditTriggers(
                QTableWidget.EditTrigger.NoEditTriggers
            )
            self.review_events_table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(self.review_events_table)
            return tab

        def _build_actions_tab(self) -> QWidget:
            tab = QScrollArea()
            content = QWidget()
            layout = QVBoxLayout(content)

            self.actions_table = QTableWidget(0, 8)
            self.actions_table.setHorizontalHeaderLabels(
                [
                    "Action",
                    "Engagement",
                    "Owner",
                    "Horizon",
                    "Due",
                    "Status",
                    "Expected outcome",
                    "Verification",
                ]
            )
            self.actions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.actions_table.horizontalHeader().setStretchLastSection(True)

            self.pilot_plan = QPlainTextEdit()
            self.pilot_plan.setReadOnly(True)
            self.pilot_plan.setMinimumHeight(180)
            self.pilot_plan.setMaximumHeight(260)

            self.delivery_outputs = QPlainTextEdit()
            self.delivery_outputs.setReadOnly(True)
            self.delivery_outputs.setMinimumHeight(220)
            self.delivery_outputs.setMaximumHeight(340)

            layout.addWidget(QLabel("Actions linked to findings, risks, or evidence gaps"))
            layout.addWidget(self.actions_table)
            self.actions_table.setSelectionBehavior(
                QTableWidget.SelectionBehavior.SelectRows
            )
            self.actions_table.itemSelectionChanged.connect(self.on_action_selected)
            self.action_detail = QPlainTextEdit()
            self.action_detail.setReadOnly(True)
            self.action_detail.setMaximumHeight(220)
            layout.addWidget(QLabel("Selected action · evidence, ownership, and verification"))
            layout.addWidget(self.action_detail)
            action_controls = QHBoxLayout()
            self.start_action_button = QPushButton("Start action")
            self.start_action_button.clicked.connect(
                lambda: self.transition_selected_action("In Progress")
            )
            self.complete_action_button = QPushButton("Report completion")
            self.complete_action_button.clicked.connect(
                lambda: self.transition_selected_action("Owner Reported Complete")
            )
            self.verify_action_button = QPushButton("Verify effectiveness")
            self.verify_action_button.clicked.connect(
                lambda: self.transition_selected_action("Verified")
            )
            action_controls.addWidget(self.start_action_button)
            action_controls.addWidget(self.complete_action_button)
            action_controls.addWidget(self.verify_action_button)
            action_controls.addStretch(1)
            layout.addLayout(action_controls)
            layout.addWidget(QLabel("Action transition audit trail"))
            self.action_events_table = QTableWidget(0, 5)
            self.action_events_table.setHorizontalHeaderLabels(
                ["Occurred (UTC)", "Event", "Actor role", "Previous status", "New status"]
            )
            self.action_events_table.setEditTriggers(
                QTableWidget.EditTrigger.NoEditTriggers
            )
            self.action_events_table.setMinimumHeight(120)
            self.action_events_table.horizontalHeader().setStretchLastSection(True)
            layout.addWidget(self.action_events_table)
            layout.addWidget(QLabel("Governance improvement and 90-day pilot"))
            layout.addWidget(self.pilot_plan)
            layout.addWidget(QLabel("Contest deliverables generated by the application"))
            layout.addWidget(self.delivery_outputs)
            tab.setWidget(content)
            tab.setWidgetResizable(True)
            return tab

        def on_role_changed(self, value: str) -> None:
            self.repo.set_setting("current_role", value)
            self.refresh_role_card()
            self.refresh_recommendation_controls()
            self.refresh_action_controls()

        def on_provider_changed(self, value: str) -> None:
            self.repo.set_setting("ai_provider", value)

        def refresh_role_card(self) -> None:
            role = self.role_combo.currentText()
            self.role_card.setText(
                f"<b>{role}</b><br>{ROLE_CAPABILITIES[role]}<br><br>"
                "<b>Demo safeguards:</b> all records and recommendations are synthetic. "
                "The provider preference is saved locally but does not connect to a model or transmit data. "
                "Role selection simulates review permissions; it is not authentication."
            )

        def refresh_all(self) -> None:
            self.refresh_role_card()
            self.refresh_portfolio_cards()
            self.refresh_portfolio_table()
            self.refresh_detail_tab()
            self.refresh_evidence_tab()
            self.refresh_ai_tab()
            self.refresh_actions_tab()
            self.refresh_recommendation_controls()

        def refresh_portfolio_cards(self) -> None:
            summary = self.repo.get_portfolio_summary()
            red = int(summary["red"])
            amber = int(summary["amber"])
            green = int(summary["green"])
            total = max(red + amber + green, 1)
            metrics = [
                ("ENGAGEMENTS", str(summary["engagements"]), "#183b58"),
                ("REPEAT FINDINGS", str(summary["repeat_findings"]), "#a95037"),
                ("OVERDUE ACTIONS", str(summary["overdue_actions"]), "#a95037"),
                ("TRACEABLE RELEASES", str(summary["traceable_releases"]), "#237d78"),
                ("GOVERNANCE BASELINE", f"{summary['governance_hours']} hrs / month", "#52657a"),
            ]
            metric_cells = "".join(
                "<td width='20%' valign='top' style='padding:8px;'>"
                "<table width='100%' cellpadding='10' cellspacing='0' "
                "style='background-color:#f5f8fb; border:1px solid #e1e8ef;'>"
                f"<tr><td><span style='color:#63768a; font-size:9pt; "
                f"font-weight:600;'>{html.escape(label)}</span><br>"
                f"<span style='color:{color}; font-size:17pt; "
                f"font-weight:700;'>{html.escape(value)}</span></td></tr></table></td>"
                for label, value, color in metrics
            )
            health_bar = (
                "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
                f"<td width='{red / total * 100:.2f}%' bgcolor='#bd5548'>&nbsp;</td>"
                f"<td width='{amber / total * 100:.2f}%' bgcolor='#d99a32'>&nbsp;</td>"
                f"<td width='{green / total * 100:.2f}%' bgcolor='#338676'>&nbsp;</td>"
                "</tr></table>"
            )
            dashboard_html = (
                "<html><body style='font-family:Segoe UI,Arial; color:#26364a; "
                "margin:0; padding:4px;'>"
                "<table width='100%' cellpadding='0' cellspacing='0'>"
                "<tr><td style='padding:3px 8px 0 8px;'>"
                "<span style='color:#183b58; font-size:15pt; font-weight:700;'>"
                "Portfolio at a glance</span><br>"
                "<span style='color:#63768a; font-size:9pt;'>"
                "Leadership view · synthetic demonstration portfolio</span></td></tr>"
                f"<tr>{metric_cells}</tr>"
                f"<tr><td colspan='5' style='padding:2px 8px 0 8px;'>{health_bar}</td></tr>"
                "<tr><td colspan='5' style='padding:5px 8px 2px 8px; "
                "color:#63768a; font-size:9pt;'>"
                f"<span style='color:#a84439; font-weight:700;'>{red} Red</span>"
                "&nbsp;&nbsp;|&nbsp;&nbsp;"
                f"<span style='color:#a46b10; font-weight:700;'>{amber} Amber</span>"
                "&nbsp;&nbsp;|&nbsp;&nbsp;"
                f"<span style='color:#247567; font-weight:700;'>{green} Green</span>"
                "&nbsp;&nbsp;&nbsp; Ratings reflect available evidence; "
                "Unknown indicates an evidence gap, not assumed failure."
                "</td></tr></table></body></html>"
            )
            self.portfolio_dashboard.setHtml(dashboard_html)

        def refresh_portfolio_table(self) -> None:
            engagements = self.repo.list_engagements(
                self.bu_filter.currentText(),
                self.status_filter.currentText(),
                self.search_filter.text(),
            )
            self.engagement_table.setRowCount(len(engagements))
            for row_index, row in enumerate(engagements):
                values = [
                    row["id"],
                    row["name"],
                    row["business_unit"],
                    row["engagement_type"],
                    row["overall_status"],
                    row["accountable_lead"],
                ]
                for column_index, value in enumerate(values):
                    self.engagement_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))

            self.engagement_table.resizeColumnsToContents()
            selected_row = 0
            for row_index in range(self.engagement_table.rowCount()):
                if self.engagement_table.item(row_index, 0).text() == self.current_engagement_id:
                    selected_row = row_index
                    break
            if self.engagement_table.rowCount() > 0:
                self.engagement_table.selectRow(selected_row)
                self.update_portfolio_side_panels()
            else:
                self.leadership_summary.setPlainText(
                    "No engagements match the current filters. "
                    f"Other tabs retain the last selected engagement ({self.current_engagement_id}) "
                    "until you clear or change the filters."
                )
                self.deliverable_summary.setPlainText(
                    "Clear the search or choose a different business unit/status to select an engagement."
                )

        def on_engagement_selected(self) -> None:
            items = self.engagement_table.selectedItems()
            if not items:
                return
            self.current_engagement_id = items[0].text()
            self.update_portfolio_side_panels()
            self.refresh_detail_tab()
            self.refresh_evidence_tab()
            self.refresh_ai_tab()
            self.refresh_actions_tab()

        def update_portfolio_side_panels(self) -> None:
            engagement = self.repo.get_engagement(self.current_engagement_id)
            if not engagement:
                return
            observations = self.repo.get_observations(self.current_engagement_id)
            evidence_lines = [
                f"- {DIMENSION_LABELS[row['dimension']]}: "
                f"{row['performance_status']} · {row['measure_value']} "
                f"(evidence: {row['evidence_confidence']}, as of {row['evidence_date']})"
                for row in observations
            ]
            actions = self.repo.get_actions(self.current_engagement_id)
            action_lines = [
                f"- {row['title']} — owner: {row['accountable_owner']}; "
                f"due {row['due_date']} ({row['status']})"
                for row in actions[:2]
            ]
            self.leadership_summary.setPlainText(
                f"Decision: {engagement['id']} · {engagement['overall_status']}\n"
                f"Why: {engagement['overview_reason']}\n\n"
                "Evidence snapshot\n"
                + "\n".join(evidence_lines)
                + "\n\nPriority actions\n"
                + ("\n".join(action_lines) if action_lines else "- No linked action is recorded.")
            )
            self.deliverable_summary.setPlainText(
                "D1 · Engineering & Service Assurance Decision Brief\n"
                "Portfolio health mix and six dimensions; explainable ratings; evidence confidence; priority risks, owners, and decisions.\n\n"
                "D2 · Governance Improvement & 90-Day Pilot Plan\n"
                "Named owners; 30/60/90-day checkpoints; review and escalation workflow; pilot baselines, proposed targets, safeguards, and Day 90 decision."
            )

        def refresh_detail_tab(self) -> None:
            engagement = self.repo.get_engagement(self.current_engagement_id)
            observations = self.repo.get_observations(self.current_engagement_id)
            if not engagement:
                return
            self.detail_header.setText(
                f"{engagement['id']} - {engagement['name']} [{engagement['overall_status']}]"
            )
            self.detail_context.setText(
                f"{engagement['engagement_type']} | {engagement['business_unit']} | Accountable lead: {engagement['accountable_lead']}\n{engagement['overview_reason']}"
            )
            self.dimension_table.setRowCount(len(observations))
            for row_index, observation in enumerate(observations):
                values = [
                    DIMENSION_LABELS[observation["dimension"]],
                    observation["measure_name"],
                    observation["measure_value"],
                    observation["performance_status"],
                    observation["evidence_confidence"],
                    observation["evidence_ref"],
                    observation["evidence_date"],
                    observation["explanation"],
                ]
                for column_index, value in enumerate(values):
                    self.dimension_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
            self.dimension_table.resizeColumnsToContents()
            derived_status, derived_reason = derive_overall_status(observations)
            self.decision_logic.setPlainText(
                f"Stored overall status: {engagement['overall_status']}\nDerived overall status: {derived_status}\nReason: {derived_reason}\n\n"
                "Rules used in this demo:\n"
                "1. Any verified Red dimension moves the engagement to Red; strong delivery in another dimension cannot hide it.\n"
                "2. If no Red is present, any Amber dimension moves the engagement to Amber.\n"
                "3. Unknown evidence remains an assurance follow-up and is shown separately from poor performance.\n"
                "4. Green is reserved for engagements with all dimensions Green and no unresolved evidence gap.\n\n"
                "Trend: no comparable prior period is supplied in this contest dataset; do not infer a trend from one observation.\n\n"
                + "\n".join(RATING_ASSUMPTIONS)
            )

        def refresh_evidence_tab(self) -> None:
            findings = self.repo.get_findings(self.current_engagement_id)
            releases = self.repo.get_releases(self.current_engagement_id)
            service_events = self.repo.get_service_events(self.current_engagement_id)
            self.findings_table.setRowCount(len(findings))
            for row_index, finding in enumerate(findings):
                values = [
                    finding["id"],
                    finding["category"],
                    finding["severity"],
                    finding["status"],
                    "Yes" if finding["repeat_flag"] else "No",
                    finding["evidence_ref"],
                    finding["opened_on"],
                ]
                for column_index, value in enumerate(values):
                    self.findings_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
            self.findings_table.resizeColumnsToContents()

            self.releases_table.setRowCount(len(releases))
            for row_index, release in enumerate(releases):
                values = [
                    release["release_name"],
                    release["deployed_on"],
                    "Yes" if release["traceable"] else "No",
                    f"{release['failure_rate']:.0f}%",
                    "Yes" if release["verified_incident"] else "No",
                    release["evidence_ref"],
                ]
                for column_index, value in enumerate(values):
                    self.releases_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
            self.releases_table.resizeColumnsToContents()

            self.service_events_table.setRowCount(len(service_events))
            for row_index, event in enumerate(service_events):
                values = [
                    event["id"],
                    f"{event['slo_name']} · {event['target_description']}",
                    f"{event['severity']} · {event['recurrence_count']} repeat(s)",
                    event["customer_impact"],
                    f"{event['assessed_penalty_units']:,.0f}",
                    f"{event['estimated_penalty_units']:,.0f}",
                    event["evidence_ref"],
                    "Verified" if event["verified"] else "Unverified",
                ]
                for column_index, value in enumerate(values):
                    self.service_events_table.setItem(
                        row_index, column_index, QTableWidgetItem(str(value))
                    )
            self.service_events_table.resizeColumnsToContents()

        def refresh_ai_tab(self) -> None:
            recommendations = self.repo.get_recommendations()
            self.recommendation_table.setRowCount(len(recommendations))
            for row_index, recommendation in enumerate(recommendations):
                values = [
                    recommendation["id"],
                    recommendation["engagement_id"],
                    recommendation["proposed_owner"],
                    f"{recommendation['horizon_days']} days",
                    recommendation["confidence"],
                    recommendation["state"],
                ]
                for column_index, value in enumerate(values):
                    self.recommendation_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
            self.recommendation_table.resizeColumnsToContents()
            if self.recommendation_table.rowCount() > 0:
                current = 0
                for row_index in range(self.recommendation_table.rowCount()):
                    if self.recommendation_table.item(row_index, 1).text() == self.current_engagement_id:
                        current = row_index
                        break
                self.recommendation_table.selectRow(current)
                self.on_recommendation_selected()

        def on_recommendation_selected(self) -> None:
            items = self.recommendation_table.selectedItems()
            if not items:
                return
            recommendation_id = items[0].text()
            with self.repo.connection() as connection:
                recommendation = connection.execute(
                    "SELECT * FROM recommendations WHERE id = ?",
                    (recommendation_id,),
                ).fetchone()
            if not recommendation:
                return
            self.recommendation_detail.setPlainText(
                textwrap.dedent(
                    f"""
                    Recommendation: {recommendation['title']}
                    Engagement: {recommendation['engagement_id']}
                    Proposed owner: {recommendation['proposed_owner']}
                    Contributors: {recommendation['contributors']}
                    Horizon: {recommendation['horizon_days']} days
                    Due date: {recommendation['due_date']}
                    Expected outcome: {recommendation['expected_outcome']}
                    Success measure: {recommendation['success_measure']}
                    Confidence: {recommendation['confidence']}
                    Current state: {recommendation['state']}

                    Rationale:
                    {recommendation['rationale']}

                    Evidence grounding:
                    {recommendation['evidence_summary']}

                    Uncertainty disclosure:
                    {recommendation['uncertainty']}
                    """
                ).strip()
            )
            review_events = self.repo.get_review_events(recommendation_id)
            self.review_events_table.setRowCount(len(review_events))
            for row_index, event in enumerate(review_events):
                values = [
                    event["occurred_at"],
                    event["event_type"],
                    event["actor_role"],
                    event["previous_state"],
                    event["new_state"],
                ]
                for column_index, value in enumerate(values):
                    self.review_events_table.setItem(
                        row_index, column_index, QTableWidgetItem(str(value))
                    )
            self.review_events_table.resizeColumnsToContents()
            self.refresh_recommendation_controls(recommendation)

        def refresh_recommendation_controls(
            self, recommendation: sqlite3.Row | None = None
        ) -> None:
            if recommendation is None:
                items = self.recommendation_table.selectedItems()
                if items:
                    with self.repo.connection() as connection:
                        recommendation = connection.execute(
                            "SELECT * FROM recommendations WHERE id = ?",
                            (items[0].text(),),
                        ).fetchone()
            reviewer = can_review_recommendations(self.role_combo.currentText())
            editable = bool(
                recommendation
                and recommendation["state"] in {"Pending Human Review", "Needs Edit"}
            )
            self.approve_button.setEnabled(reviewer and editable)
            self.reject_button.setEnabled(reviewer and editable)
            self.edit_button.setEnabled(reviewer and editable)
            self.return_button.setEnabled(
                reviewer
                and recommendation is not None
                and recommendation["state"] == "Pending Human Review"
            )

        def change_recommendation_state(self, state: str) -> None:
            items = self.recommendation_table.selectedItems()
            if not items:
                return
            recommendation_id = items[0].text()
            if not can_review_recommendations(self.role_combo.currentText()):
                QMessageBox.warning(
                    self,
                    "Role restriction",
                    "Only the sponsor or delivery assurance leader can review a recommendation.",
                )
                return
            try:
                self.repo.update_recommendation_state(
                    recommendation_id, state, self.role_combo.currentText()
                )
            except (PermissionError, ValueError) as error:
                QMessageBox.warning(self, "Recommendation not updated", str(error))
                return
            self.refresh_ai_tab()
            self.refresh_actions_tab()

        def edit_recommendation(self) -> None:
            items = self.recommendation_table.selectedItems()
            if not items:
                return
            recommendation_id = items[0].text()
            with self.repo.connection() as connection:
                recommendation = connection.execute(
                    "SELECT * FROM recommendations WHERE id = ?",
                    (recommendation_id,),
                ).fetchone()
            if not recommendation:
                QMessageBox.warning(
                    self, "Recommendation not found", recommendation_id
                )
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Edit proposal before approval")
            form = QFormLayout(dialog)
            title = QLineEdit(recommendation["title"])
            owner = QComboBox()
            owner.addItems(list(ROLE_CAPABILITIES))
            owner.setCurrentText(recommendation["proposed_owner"])
            contributors = QLineEdit(recommendation["contributors"])
            horizon = QComboBox()
            horizon.addItems(["30", "60", "90"])
            horizon.setCurrentText(str(recommendation["horizon_days"]))
            due_date = QLineEdit(recommendation["due_date"])
            due_date.setPlaceholderText("YYYY-MM-DD")
            outcome = QPlainTextEdit(recommendation["expected_outcome"])
            measure = QLineEdit(recommendation["success_measure"])
            form.addRow("Action", title)
            form.addRow("One accountable owner", owner)
            form.addRow("Contributors (optional)", contributors)
            form.addRow("Horizon (days)", horizon)
            form.addRow("Due date", due_date)
            form.addRow("Expected outcome", outcome)
            form.addRow("Success measure", measure)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save
                | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            fields: dict[str, str | int] = {
                "title": title.text(),
                "proposed_owner": owner.currentText(),
                "contributors": contributors.text(),
                "horizon_days": int(horizon.currentText()),
                "due_date": due_date.text().strip(),
                "expected_outcome": outcome.toPlainText(),
                "success_measure": measure.text(),
            }
            try:
                self.repo.update_recommendation_details(
                    recommendation_id, fields, self.role_combo.currentText()
                )
            except (PermissionError, ValueError) as error:
                QMessageBox.warning(self, "Proposal not saved", str(error))
                return
            self.refresh_ai_tab()
            self.refresh_actions_tab()

        def refresh_actions_tab(self) -> None:
            actions = self.repo.get_actions()
            self.actions_table.setRowCount(len(actions))
            for row_index, action in enumerate(actions):
                values = [
                    action["id"],
                    action["engagement_id"],
                    action["accountable_owner"],
                    f"{action['horizon_days']} days",
                    action["due_date"],
                    action["status"],
                    action["expected_outcome"],
                    action["verified_effectiveness"],
                ]
                for column_index, value in enumerate(values):
                    self.actions_table.setItem(row_index, column_index, QTableWidgetItem(str(value)))
            self.actions_table.resizeColumnsToContents()
            selected_row = 0
            for row_index, action in enumerate(actions):
                if action["id"] == self.current_action_id:
                    selected_row = row_index
                    break
            if actions:
                self.actions_table.selectRow(selected_row)
                self.on_action_selected()
            else:
                self.current_action_id = None
                self.action_detail.clear()
                self.action_events_table.setRowCount(0)
                self.refresh_action_controls()
            self.pilot_plan.setPlainText(self.repo.build_pilot_plan())
            self.delivery_outputs.setPlainText(
                self.repo.build_decision_brief()
                + "\n\n"
                + self.repo.build_pilot_plan()
            )

        def on_action_selected(self) -> None:
            items = self.actions_table.selectedItems()
            if not items:
                return
            self.current_action_id = items[0].text()
            action = next(
                (
                    row
                    for row in self.repo.get_actions()
                    if row["id"] == self.current_action_id
                ),
                None,
            )
            if not action:
                return
            self.action_detail.setPlainText(
                f"Action: {action['title']}\n"
                f"Engagement: {action['engagement_id']}\n"
                f"Triggering risk/evidence: {action['trigger_ref']}\n"
                f"Accountable owner: {action['accountable_owner']}\n"
                f"Contributors: {action['contributors'] or 'None listed'}\n"
                f"Horizon / due date: {action['horizon_days']} days / {action['due_date']}\n"
                f"Expected outcome: {action['expected_outcome']}\n"
                f"Success measure: {action['success_measure']}\n"
                f"Status: {action['status']}\n"
                f"Escalation condition: {action['escalation_condition']}\n"
                f"Owner completion evidence: {action['completion_evidence']}\n"
                f"Independent effectiveness verification: {action['verified_effectiveness']}"
            )
            events = self.repo.get_action_events(self.current_action_id)
            self.action_events_table.setRowCount(len(events))
            for row_index, event in enumerate(events):
                values = [
                    event["occurred_at"],
                    event["event_type"],
                    event["actor_role"],
                    event["previous_status"],
                    event["new_status"],
                ]
                for column_index, value in enumerate(values):
                    self.action_events_table.setItem(
                        row_index, column_index, QTableWidgetItem(str(value))
                    )
            self.action_events_table.resizeColumnsToContents()
            self.refresh_action_controls(action)

        def refresh_action_controls(
            self, action: sqlite3.Row | None = None
        ) -> None:
            if action is None and self.current_action_id:
                action = next(
                    (
                        row
                        for row in self.repo.get_actions()
                        if row["id"] == self.current_action_id
                    ),
                    None,
                )
            role = self.role_combo.currentText()
            owner_role = bool(action and role == action["accountable_owner"])
            status = action["status"] if action else ""
            self.start_action_button.setEnabled(
                owner_role and status == "Approved"
            )
            self.complete_action_button.setEnabled(
                owner_role and status == "In Progress"
            )
            self.verify_action_button.setEnabled(
                status == "Owner Reported Complete"
                and role
                in {"Delivery Assurance Leader", "Auditor / Control Reviewer"}
            )

        def transition_selected_action(self, new_status: str) -> None:
            if not self.current_action_id:
                return
            evidence = ""
            if new_status in {"Owner Reported Complete", "Verified"}:
                prompt = (
                    "Describe the completion evidence."
                    if new_status == "Owner Reported Complete"
                    else "Record the independent evidence that verifies effectiveness."
                )
                evidence, accepted = QInputDialog.getMultiLineText(
                    self, new_status, prompt
                )
                if not accepted:
                    return
            try:
                self.repo.transition_action(
                    self.current_action_id,
                    new_status,
                    self.role_combo.currentText(),
                    evidence,
                )
            except (PermissionError, ValueError) as error:
                QMessageBox.warning(self, "Action not updated", str(error))
                return
            self.refresh_actions_tab()

        def export_pack(self) -> None:
            exported = self.repo.export_decision_pack()
            QMessageBox.information(
                self,
                "PS03 outputs exported",
                "\n".join(str(path) for path in exported),
            )

        def run_validation_dialog(self) -> None:
            issues = validate_dataset(self.repo)
            if issues:
                QMessageBox.critical(self, "Validation failed", "\n".join(issues))
                return
            QMessageBox.information(
                self,
                "Validation passed",
                "Portfolio facts, rating logic, and exemplar cases reconcile with the contest brief.",
            )

    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QWidget { font-family: "Segoe UI"; font-size: 12px; color: #26364a; }
        QMainWindow, QWidget#mainContainer { background: #f2f5f9; }
        QWidget#executiveHeader { background: #132b45; border: 1px solid #203e5e; border-radius: 12px; }
        QLabel#headerEyebrow { color: #8bd1cc; font-size: 10px; font-weight: 700; }
        QLabel#headerTitle { color: #ffffff; font-size: 25px; font-weight: 700; }
        QLabel#headerSubtitle { color: #d3deea; font-size: 12px; }
        QLabel#portfolioContext { background: #e8f1f5; color: #26465a; border: 1px solid #d5e4eb; border-radius: 7px; padding: 9px 12px; }
        QLabel#roleNotice { background: #ffffff; color: #34485c; border: 1px solid #d8e1ea; border-left: 4px solid #23827f; border-radius: 7px; padding: 9px 12px; }
        QGroupBox { background: #ffffff; font-weight: 600; color: #52657a; border: 1px solid #dce4ec; border-radius: 9px; margin-top: 8px; padding-top: 12px; }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
        QTextBrowser#portfolioDashboard { background: #ffffff; border: 1px solid #dce4ec; border-radius: 8px; }
        QTabWidget::pane { background: #ffffff; border: 1px solid #dce4ec; border-radius: 8px; top: -1px; }
        QTabBar::tab { background: #e8edf3; color: #45596f; padding: 10px 15px; margin-right: 4px; border-top-left-radius: 6px; border-top-right-radius: 6px; }
        QTabBar::tab:selected { background: #ffffff; color: #142f4b; font-weight: 700; border: 1px solid #dce4ec; border-bottom-color: #ffffff; }
        QHeaderView::section { background: #e9eff5; color: #30465c; padding: 8px 7px; font-weight: 700; border: none; border-bottom: 1px solid #d5dfe8; }
        QTableWidget { background: #ffffff; alternate-background-color: #f7f9fb; gridline-color: #edf1f5; border: 1px solid #dce4ec; border-radius: 6px; selection-background-color: #dcecf2; selection-color: #142f4b; }
        QTableWidget::item { padding: 5px; }
        QLineEdit, QComboBox, QTextEdit, QPlainTextEdit { background: #ffffff; color: #26364a; border: 1px solid #cbd6e1; border-radius: 6px; padding: 6px 8px; selection-background-color: #cfe3eb; }
        QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus { border: 1px solid #23827f; }
        QPushButton { background: #176f70; color: #ffffff; border: 1px solid #176f70; border-radius: 6px; padding: 8px 12px; font-weight: 600; }
        QPushButton:hover { background: #125d60; }
        QPushButton:pressed { background: #0f4e52; }
        QPushButton:disabled { background: #aab6c2; color: #f4f6f8; border-color: #aab6c2; }
        QMenuBar { background: #ffffff; color: #26364a; }
        QMenuBar::item:selected, QMenu::item:selected { background: #e8f1f5; }
        """
    )
    window = MainWindow(repo)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run_cli(sys.argv[1:]))
