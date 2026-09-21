# SmartCart — Intelligent Grocery Store Management System

A beginner-friendly Flask and SQLite grocery store platform with authentication, inventory, customer and supplier records, point-of-sale billing, reporting, and responsive Bootstrap UI.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http127.0.0.1:5000

Demo login: `admin` / `admin123`

The SQLite database is created and seeded automatically on first launch. The app contains 15 products, 5 customers, 5 suppliers, and a working billing flow. New sales created through Billing immediately reduce inventory and appear in Sales and Reports.
