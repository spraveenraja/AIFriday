# PS03 Assurance Studio

PySide6 desktop demonstration for Problem Statement 03: `Software Quality, Engagement Health & Delivery Assurance`.

The project is aligned to the contest workbook and the supplied implementation brief:

- Uses synthetic data only.
- Preserves the supplied PS03 case facts.
- Centers the UI around the two mandatory PS03 outputs:
  - `Engineering & Service Assurance Decision Brief`
  - `Governance Improvement & 90-Day Pilot Plan`
- Uses SQLite for the seeded demonstration data.
- Keeps the AI provider configurable without embedding any API keys.

## What the app includes

- Executive portfolio dashboard with PS03 fact reconciliation.
- Engagement detail view with six dimensions, explainable rules, evidence source/date, and separate evidence confidence. No trend is inferred without a comparable prior period.
- Evidence and findings view linking findings, release samples, and traceability.
- SLO event view covering severity, recurrence, customer impact, and estimated or assessed synthetic penalty units.
- AI recommendation review with editable proposals, human approval/rejection, action activation, and a reviewer audit trail.
- 30/60/90-day action and pilot view with role-gated `Approved → In Progress → Owner Reported Complete → Verified` transitions and action audit history.
- Export of the two PS03 contest outputs to `exports/`.

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Run the desktop app

```powershell
python app.py
```

If you want to rebuild the SQLite seed first:

```powershell
python app.py --reset-db
```

`--reset-db` rebuilds the demo database and resets saved demo preferences/review decisions. The app migrates the earlier seed version without deleting the database.

## Validation

Runs reconciliation checks for the supplied case facts and exemplar engagements `ENG-007` and `SRV-012`.

```powershell
python app.py --validate
```

Only add `--reset-db` when you intentionally want to rebuild the demo database and clear saved review decisions/preferences.

Run focused application tests:

```powershell
python -m unittest discover -s tests -v
```

## Export the contest outputs

```powershell
python app.py --export-pack
```

This writes:

- `exports/03_D1_Engineering_and_Service_Assurance_Decision_Brief.txt`
- `exports/03_D2_Governance_Improvement_and_90_Day_Pilot_Plan.txt`

## Notes

- Thresholds in the app are treated as contest-demo assumptions, not contract or industry standards.
- Missing, stale, or unverified evidence is shown as `Unknown` for the affected measure and is not automatically treated as poor performance.
- SLO breach severity, recurrence, customer impact, and penalty exposure are shown as synthetic evidence; penalty units are not real prices or contract values.
- The AI workflow is intentionally constrained: recommendations are synthetic, evidence-cited, and require human approval before a linked draft action becomes active.
- The provider selector only stores a local demo preference; there is no model connection, API request, or external data transfer. The role selector simulates permissions and is not authentication.
- The portfolio denominator choices (11/50 findings, 9/29 actions, and 16/25 releases) are illustrative synthetic choices used to reconcile the supplied percentages.
