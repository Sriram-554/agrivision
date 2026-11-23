# AgriVision - IoT Crop Yield Monitoring Demo

A complete Flask and SQLite/HTML/CSS/JavaScript demonstration dashboard for an academic Software Engineering project.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

## Demo credentials

- Farmer: `farmer@agrivision.demo` / `farmer123`
- Admin: `admin@agrivision.demo` / `admin123`

## Demo boundaries

- Sensor readings are simulated.
- The ESP32 is simulated only.
- Yield predictions use a clearly labelled demonstration formula, not a trained model.
- No model accuracy or real-hardware claim is made.

## Database

The local setup uses `data/crop_monitor.db` automatically. Set `MYSQL_HOST` and `MYSQL_DATABASE` environment variables to enable the MySQL-ready branch. Credentials must remain in environment variables.

`database.py` contains the required schema structure for users, farms, sensor devices, sensor readings, crop seasons, yield predictions, alerts, and settings.
