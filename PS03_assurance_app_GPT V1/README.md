# Delivery Assurance Executive App

A synthetic-data desktop demonstration for Software Quality, Engagement Health & Delivery Assurance.

## Features

- Executive portfolio dashboard with engagement health mix and operating indicators.
- Engagement search, filters, and evidence-backed detail views.
- Synthetic release samples, findings, SLO breaches, and traceability records.
- Evidence-grounded AI recommendation review with human accept/reject controls.
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

## Synthetic data and demo assumptions

Every record is invented and labeled synthetic. The seed data preserves the supplied portfolio facts: 28 engagements across five invented units; 4 Red, 9 Amber, 15 Green; 11 of 50 repeated findings; 9 of 29 initially overdue actions; 16 of 25 sampled releases fully traceable; and 240 governance hours per month as a case baseline. Percentage denominators are illustrative synthetic choices. Thresholds are contest-demo assumptions, not industry benchmarks or client contract terms.

The app includes seeded synthetic recommendation drafts for offline demonstration. It can also call an OpenAI Responses API model when configured through environment variables. Live requests use only the selected engagement's synthetic demo context; recommendations must cite evidence IDs returned with that context and pass validation before they are saved. Human review is still required before an accepted recommendation becomes an action. No API key is stored in the app or SQLite.

To enable live AI in PowerShell, set the key and model in the same terminal before launching:

```powershell
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_MODEL = "your-model"
# Optional for a compatible gateway
$env:OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
python app.py
```

Live model use may incur provider charges. Keep this contest demo synthetic; do not enter or send real or confidential data.

## Local database

On first run the app creates `data/assurance_demo.sqlite3` beside the source files. It remains local to this project. To restore the original synthetic fixtures, close the app and delete that database; the next launch will recreate it.
