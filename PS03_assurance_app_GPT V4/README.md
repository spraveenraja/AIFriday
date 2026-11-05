# Delivery Assurance Executive App

A synthetic-data desktop demonstration for Software Quality, Engagement Health & Delivery Assurance.

## Features

- Rich executive dashboard with portfolio-health chart, assurance signals, and priority engagements.
- Scrollable dashboard content and readable tables with internal scrolling, wrapping, and cell tooltips.
- Engagement search, filters, and evidence-backed detail views.
- Synthetic release samples, findings, SLO breaches, and traceability records.
- Evidence-grounded recommendation review with sentence-case Accept, Reject, and Edit controls.
- Persona-tailored recommendation guidance for executive sponsors, delivery assurance, account, engineering, service, risk/compliance, and commercial/finance roles.
- Polite, neutral assurance chatbot with offline answers and optional live model responses.
- Action plan grouped by 30, 60, and 90-day horizons.
- Local SQLite database created and seeded on first launch.

## Requirements

- Python 3.10 or later
- PySide6

## Run in VS Code / PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks virtual environment activation, use `\.venv\Scripts\python.exe -m pip install -r requirements.txt` and then `\.venv\Scripts\python.exe app.py`.

## AI model settings

The app reads settings from `secrets.toml` in the project root, or `.streamlit/secrets.toml`. Copy `secrets.example.toml` to `secrets.toml`, then set:

```toml
[ai]
provider = "openai"
api_key = "your-key"
model = "your-model"
responses_url = "https://api.openai.com/v1/responses"
```

Environment variables `OPENAI_API_KEY`, `OPENAI_MODEL`, and `OPENAI_RESPONSES_URL` override file values. The app does not display or save the key. A live chat or recommendation request sends only the selected synthetic engagement context. Never put real or confidential records into this contest demonstration. Live model use may incur provider charges.

Without model settings, the app uses seeded synthetic recommendation drafts and a small local answer set for the chatbot. The UI labels offline responses clearly.

## Synthetic data and demo assumptions

Every record is invented and labeled synthetic. The seed data preserves the supplied portfolio facts: 28 engagements across five invented units; 4 Red, 9 Amber, 15 Green; 11 of 50 repeated findings; 9 of 29 initially overdue actions; 16 of 25 sampled releases fully traceable; and 240 governance hours per month as a case baseline. Percentage denominators are illustrative synthetic choices. Thresholds are contest-demo assumptions, not industry benchmarks or client contract terms.

## Local database

On first run the app creates `data/assurance_demo.sqlite3` beside the source files. To restore the original synthetic fixtures, close the app and delete that database; the next launch will recreate it.
