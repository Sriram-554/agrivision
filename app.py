import os
import random
from datetime import datetime, timedelta

from flask import Flask, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from database import get_connection, initialize_database
from model import predict_yield_demo

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-this-in-production")

initialize_database()


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def dict_rows(rows):
    return [dict(row) for row in rows]


def seed_demo_data():
    with get_connection() as conn:
        cur = conn.execute("SELECT COUNT(*) AS count FROM users")
        if cur.fetchone()["count"] == 0:
            conn.execute(
                "INSERT INTO users (name,email,password_hash,role,phone,location) VALUES (?,?,?,?,?,?)",
                ("Arjun Patel", "farmer@agrivision.demo", generate_password_hash("farmer123"), "farmer",
                 "+91 98765 43210", "Nashik, Maharashtra"),
            )
            conn.execute(
                "INSERT INTO users (name,email,password_hash,role,phone,location) VALUES (?,?,?,?,?,?)",
                ("Demo Administrator", "admin@agrivision.demo", generate_password_hash("admin123"), "admin",
                 "+91 98765 43000", "Pune, Maharashtra"),
            )
            farmer = conn.execute("SELECT id FROM users WHERE email=?", ("farmer@agrivision.demo",)).fetchone()
            admin = conn.execute("SELECT id FROM users WHERE email=?", ("admin@agrivision.demo",)).fetchone()
            conn.execute(
                "INSERT INTO farms (user_id,name,location,area,crop_type,created_at) VALUES (?,?,?,?,?,?)",
                (farmer["id"], "Green Valley Farm", "Nashik, Maharashtra", 12.5, "Rice", now_iso()),
            )
            conn.execute(
                "INSERT INTO farms (user_id,name,location,area,crop_type,created_at) VALUES (?,?,?,?,?,?)",
                (farmer["id"], "Sunrise Orchard", "Sinnar, Maharashtra", 8.0, "Tomato", now_iso()),
            )
            conn.execute(
                "INSERT INTO app_settings (user_id,moisture_threshold,temperature_threshold) VALUES (?,?,?)",
                (farmer["id"], 30, 35),
            )
            conn.execute(
                "INSERT INTO app_settings (user_id,moisture_threshold,temperature_threshold) VALUES (?,?,?)",
                (admin["id"], 30, 35),
            )
            farm = conn.execute("SELECT id FROM farms WHERE name=?", ("Green Valley Farm",)).fetchone()
            conn.execute(
                "INSERT INTO sensor_devices (device_id,name,farm_id,status,last_communication) VALUES (?,?,?,?,?)",
                ("ESP32-DEMO-001", "Green Valley Sensor Hub", farm["id"], "online", now_iso()),
            )
            device = conn.execute("SELECT id FROM sensor_devices WHERE device_id=?", ("ESP32-DEMO-001",)).fetchone()
            start = datetime.now() - timedelta(hours=168)
            for i in range(169):
                stamp = (start + timedelta(hours=i)).isoformat(timespec="seconds")
                conn.execute(
                    "INSERT INTO sensor_readings (device_id,farm_id,soil_moisture,temperature,humidity,light_intensity,recorded_at) VALUES (?,?,?,?,?,?,?)",
                    (device["id"], farm["id"],
                     round(54 + random.uniform(-8, 8), 1),
                     round(26 + random.uniform(-3, 4), 1),
                     round(68 + random.uniform(-7, 7), 1),
                     round(random.uniform(300, 4200), 0), stamp),
                )
            conn.execute(
                "INSERT INTO alerts (user_id,farm_id,title,message,severity,is_read,created_at) VALUES (?,?,?,?,?,?,?)",
                (farmer["id"], farm["id"], "New sensor data received",
                 "The demo ESP32 device reported a fresh set of readings.", "info", 0, now_iso()),
            )
            conn.execute(
                "INSERT INTO alerts (user_id,farm_id,title,message,severity,is_read,created_at) VALUES (?,?,?,?,?,?,?)",
                (farmer["id"], farm["id"], "Soil moisture in normal range",
                 "Current soil moisture is above the configured 30% threshold.", "success", 1,
                 (datetime.now() - timedelta(minutes=18)).isoformat(timespec="seconds")),
            )
            conn.commit()


seed_demo_data()


@app.after_request
def add_no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/auth/status")
def auth_status():
    if "user_id" not in session:
        return jsonify({"authenticated": False})
    with get_connection() as conn:
        user = conn.execute("SELECT id,name,email,role FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return jsonify({"authenticated": True, "user": dict(user) if user else None})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
    with get_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401
    session["user_id"] = user["id"]
    session["role"] = user["role"]
    return jsonify({"message": "Login successful.", "user": {
        "id": user["id"], "name": user["name"], "email": user["email"], "role": user["role"]
    }})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


def require_login():
    if "user_id" not in session:
        return jsonify({"error": "Authentication required."}), 401
    return None


@app.route("/api/dashboard")
def dashboard():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    with get_connection() as conn:
        farms = conn.execute("SELECT * FROM farms WHERE user_id=?", (uid,)).fetchall()
        farm_ids = [f["id"] for f in farms]
        devices = conn.execute(
            "SELECT * FROM sensor_devices WHERE farm_id IN ({})".format(",".join("?" for _ in farm_ids)),
            farm_ids,
        ).fetchall() if farm_ids else []
        reading = None
        if farm_ids:
            reading = conn.execute(
                "SELECT * FROM sensor_readings WHERE farm_id IN ({}) ORDER BY recorded_at DESC LIMIT 1".format(
                    ",".join("?" for _ in farm_ids)), farm_ids
            ).fetchone()
        prediction = conn.execute(
            "SELECT * FROM yield_predictions WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (uid,)
        ).fetchone()
        alerts = conn.execute(
            "SELECT * FROM alerts WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (uid,)
        ).fetchall()
    return jsonify({
        "total_farms": len(farms),
        "active_devices": sum(1 for d in devices if d["status"] == "online"),
        "reading": dict(reading) if reading else None,
        "latest_yield": dict(prediction) if prediction else None,
        "alerts": dict_rows(alerts),
        "devices": dict_rows(devices),
    })


@app.route("/api/farms", methods=["GET", "POST"])
def farms():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    if request.method == "GET":
        with get_connection() as conn:
            rows = conn.execute("SELECT * FROM farms WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()
        return jsonify({"farms": dict_rows(rows)})
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    location = str(data.get("location", "")).strip()
    crop_type = str(data.get("crop_type", "")).strip()
    try:
        area = float(data.get("area", 0))
    except (TypeError, ValueError):
        area = 0
    if not name or not location or not crop_type or area <= 0:
        return jsonify({"error": "Name, location, crop type, and a positive area are required."}), 400
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO farms (user_id,name,location,area,crop_type,created_at) VALUES (?,?,?,?,?,?)",
            (uid, name, location, area, crop_type, now_iso()),
        )
        conn.commit()
    return jsonify({"message": "Farm added successfully."}), 201


@app.route("/api/farms/<int:farm_id>", methods=["PUT", "DELETE"])
def farm_detail(farm_id):
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    with get_connection() as conn:
        farm = conn.execute("SELECT * FROM farms WHERE id=? AND user_id=?", (farm_id, uid)).fetchone()
        if not farm:
            return jsonify({"error": "Farm not found."}), 404
        if request.method == "DELETE":
            conn.execute("DELETE FROM farms WHERE id=?", (farm_id,))
            conn.commit()
            return jsonify({"message": "Farm deleted successfully."})
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        location = str(data.get("location", "")).strip()
        crop_type = str(data.get("crop_type", "")).strip()
        try:
            area = float(data.get("area", 0))
        except (TypeError, ValueError):
            area = 0
        if not name or not location or not crop_type or area <= 0:
            return jsonify({"error": "All farm fields are required and area must be positive."}), 400
        conn.execute(
            "UPDATE farms SET name=?,location=?,area=?,crop_type=? WHERE id=?",
            (name, location, area, crop_type, farm_id),
        )
        conn.commit()
    return jsonify({"message": "Farm updated successfully."})


@app.route("/api/readings/latest")
def latest_reading():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    with get_connection() as conn:
        farms = conn.execute("SELECT id FROM farms WHERE user_id=?", (uid,)).fetchall()
        farm_ids = [f["id"] for f in farms]
        device = None
        reading = None
        if farm_ids:
            placeholders = ",".join("?" for _ in farm_ids)
            device = conn.execute(
                "SELECT * FROM sensor_devices WHERE farm_id IN ({}) ORDER BY id DESC LIMIT 1".format(placeholders),
                farm_ids,
            ).fetchone()
            reading = conn.execute(
                "SELECT * FROM sensor_readings WHERE farm_id IN ({}) ORDER BY recorded_at DESC LIMIT 1".format(placeholders),
                farm_ids,
            ).fetchone()
    if not reading:
        return jsonify({"reading": None, "device": dict(device) if device else None})
    return jsonify({"reading": dict(reading), "device": dict(device) if device else None})


@app.route("/api/readings/simulate", methods=["POST"])
def simulate_reading():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    with get_connection() as conn:
        farm = conn.execute("SELECT id FROM farms WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,)).fetchone()
        if not farm:
            return jsonify({"error": "Add a farm before generating sensor data."}), 400
        device = conn.execute(
            "SELECT * FROM sensor_devices WHERE farm_id=? ORDER BY id DESC LIMIT 1", (farm["id"],)
        ).fetchone()
        if not device:
            device_id = "ESP32-DEMO-001"
            existing = conn.execute("SELECT * FROM sensor_devices WHERE device_id=?", (device_id,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE sensor_devices SET farm_id=?,status='online',last_communication=? WHERE id=?",
                    (farm["id"], now_iso(), existing["id"]),
                )
                conn.commit()
                device = conn.execute("SELECT * FROM sensor_devices WHERE id=?", (existing["id"],)).fetchone()
            else:
                conn.execute(
                    "INSERT INTO sensor_devices (device_id,name,farm_id,status,last_communication) VALUES (?,?,?,?,?)",
                    (device_id, "Demo ESP32 Sensor", farm["id"], "online", now_iso()),
                )
                conn.commit()
                device = conn.execute("SELECT * FROM sensor_devices WHERE device_id=?", (device_id,)).fetchone()
        if device["status"] != "online":
            return jsonify({"error": "The demo sensor is offline. Set it online in Device Management."}), 409
        reading = {
            "soil_moisture": round(random.uniform(28, 72), 1),
            "temperature": round(random.uniform(20, 38), 1),
            "humidity": round(random.uniform(45, 85), 1),
            "light_intensity": round(random.uniform(250, 5200), 0),
        }
        stamp = now_iso()
        conn.execute(
            "INSERT INTO sensor_readings (device_id,farm_id,soil_moisture,temperature,humidity,light_intensity,recorded_at) VALUES (?,?,?,?,?,?,?)",
            (device["id"], farm["id"], reading["soil_moisture"], reading["temperature"],
             reading["humidity"], reading["light_intensity"], stamp),
        )
        conn.execute("UPDATE sensor_devices SET last_communication=? WHERE id=?", (stamp, device["id"]))
        settings = conn.execute(
            "SELECT moisture_threshold,temperature_threshold FROM app_settings WHERE user_id=?", (uid,)
        ).fetchone()
        moisture_limit = settings["moisture_threshold"] if settings else 30
        temp_limit = settings["temperature_threshold"] if settings else 35
        if reading["soil_moisture"] < moisture_limit:
            conn.execute(
                "INSERT INTO alerts (user_id,farm_id,title,message,severity,is_read,created_at) VALUES (?,?,?,?,?,?,?)",
                (uid, farm["id"], "Low soil moisture",
                 "Soil moisture dropped below the configured threshold.", "warning", 0, stamp),
            )
        if reading["temperature"] > temp_limit:
            conn.execute(
                "INSERT INTO alerts (user_id,farm_id,title,message,severity,is_read,created_at) VALUES (?,?,?,?,?,?,?)",
                (uid, farm["id"], "High temperature",
                 "Temperature exceeded the configured threshold.", "danger", 0, stamp),
            )
        conn.execute(
            "INSERT INTO alerts (user_id,farm_id,title,message,severity,is_read,created_at) VALUES (?,?,?,?,?,?,?)",
            (uid, farm["id"], "New sensor data received",
             "A fresh set of simulated sensor readings was generated.", "info", 0, stamp),
        )
        conn.commit()
    reading["recorded_at"] = stamp
    return jsonify({"message": "Simulated sensor data received.", "reading": reading})


@app.route("/api/readings/history")
def history():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    period = int(request.args.get("hours", 24))
    period = period if period in (24, 72, 168) else 24
    cutoff = (datetime.now() - timedelta(hours=period)).isoformat(timespec="seconds")
    with get_connection() as conn:
        farms = conn.execute("SELECT id FROM farms WHERE user_id=?", (uid,)).fetchall()
        farm_ids = [f["id"] for f in farms]
        if farm_ids:
            placeholders = ",".join("?" for _ in farm_ids)
            rows = conn.execute(
                "SELECT * FROM sensor_readings WHERE farm_id IN ({}) AND recorded_at>=? ORDER BY recorded_at ASC".format(placeholders),
                farm_ids + [cutoff],
            ).fetchall()
        else:
            rows = []
    return jsonify({"readings": dict_rows(rows)})


@app.route("/api/predict", methods=["POST"])
def predict():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    try:
        farm_id = int(data.get("farm_id"))
        area = float(data.get("area"))
        soil = float(data.get("soil_moisture"))
        temperature = float(data.get("temperature"))
        humidity = float(data.get("humidity"))
    except (TypeError, ValueError):
        return jsonify({"error": "All prediction fields must contain valid numbers."}), 400
    crop = str(data.get("crop_type", "")).strip()
    if not crop or area <= 0 or soil < 0 or soil > 100 or humidity < 0 or humidity > 100:
        return jsonify({"error": "Enter a crop and valid area, moisture, temperature, and humidity values."}), 400
    estimated = predict_yield_demo(crop, area, soil, temperature, humidity)
    stamp = now_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO yield_predictions (user_id,farm_id,crop_type,area,soil_moisture,temperature,humidity,estimated_yield,unit,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (uid, farm_id, crop, area, soil, temperature, humidity, estimated,
             "tonnes" if crop not in ("Sugarcane",) else "tonnes", stamp),
        )
        conn.commit()
    return jsonify({
        "estimated_yield": estimated,
        "unit": "tonnes",
        "timestamp": stamp,
        "demo": True,
        "message": "Demonstration estimate generated. This is not a trained-model prediction.",
    })


@app.route("/api/alerts", methods=["GET"])
def alerts():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM alerts WHERE user_id=? ORDER BY created_at DESC", (uid,)).fetchall()
    return jsonify({"alerts": dict_rows(rows)})


@app.route("/api/alerts/<int:alert_id>/read", methods=["PUT"])
def mark_alert_read(alert_id):
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    with get_connection() as conn:
        conn.execute("UPDATE alerts SET is_read=1 WHERE id=? AND user_id=?", (alert_id, uid))
        conn.commit()
    return jsonify({"message": "Alert marked as read."})


@app.route("/api/devices")
def devices():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT d.*, f.name AS farm_name
               FROM sensor_devices d
               LEFT JOIN farms f ON d.farm_id=f.id
               WHERE f.user_id=? OR d.farm_id IS NULL""",
            (uid,),
        ).fetchall()
    return jsonify({"devices": dict_rows(rows)})


@app.route("/api/devices/<int:device_id>/status", methods=["PUT"])
def device_status(device_id):
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("online", "offline"):
        return jsonify({"error": "Status must be online or offline."}), 400
    stamp = now_iso() if status == "online" else None
    with get_connection() as conn:
        device = conn.execute(
            "SELECT d.* FROM sensor_devices d JOIN farms f ON d.farm_id=f.id WHERE d.id=? AND f.user_id=?",
            (device_id, uid),
        ).fetchone()
        if not device:
            return jsonify({"error": "Device not found."}), 404
        conn.execute(
            "UPDATE sensor_devices SET status=?,last_communication=? WHERE id=?",
            (status, stamp or device["last_communication"], device_id),
        )
        if status == "offline":
            conn.execute(
                "INSERT INTO alerts (user_id,farm_id,title,message,severity,is_read,created_at) VALUES (?,?,?,?,?,?,?)",
                (uid, device["farm_id"], "Sensor connection lost",
                 "The simulated device was switched offline.", "danger", 0, now_iso()),
            )
        else:
            conn.execute(
                "INSERT INTO alerts (user_id,farm_id,title,message,severity,is_read,created_at) VALUES (?,?,?,?,?,?,?)",
                (uid, device["farm_id"], "Sensor connection restored",
                 "The simulated device is online again.", "success", 0, now_iso()),
            )
        conn.commit()
    return jsonify({"message": f"Device is now {status}.", "status": status})


@app.route("/api/settings", methods=["GET", "PUT"])
def settings():
    denied = require_login()
    if denied:
        return denied
    uid = session["user_id"]
    with get_connection() as conn:
        user = conn.execute("SELECT id,name,email,role,phone,location FROM users WHERE id=?", (uid,)).fetchone()
        settings_row = conn.execute(
            "SELECT moisture_threshold,temperature_threshold FROM app_settings WHERE user_id=?", (uid,)
        ).fetchone()
        if not settings_row:
            conn.execute(
                "INSERT INTO app_settings (user_id,moisture_threshold,temperature_threshold) VALUES (?,?,?)",
                (uid, 30, 35),
            )
            conn.commit()
            settings_row = {"moisture_threshold": 30, "temperature_threshold": 35}
        if request.method == "GET":
            return jsonify({
                "profile": dict(user),
                "settings": dict(settings_row),
            })
        data = request.get_json(silent=True) or {}
        name = str(data.get("name", "")).strip()
        phone = str(data.get("phone", "")).strip()
        location = str(data.get("location", "")).strip()
        try:
            moisture = float(data.get("moisture_threshold", 30))
            temperature = float(data.get("temperature_threshold", 35))
        except (TypeError, ValueError):
            return jsonify({"error": "Threshold values must be numbers."}), 400
        if not name or moisture < 0 or moisture > 100 or temperature < -20 or temperature > 60:
            return jsonify({"error": "Enter a valid name and threshold values."}), 400
        conn.execute(
            "UPDATE users SET name=?,phone=?,location=? WHERE id=?",
            (name, phone, location, uid),
        )
        conn.execute(
            "UPDATE app_settings SET moisture_threshold=?,temperature_threshold=? WHERE user_id=?",
            (moisture, temperature, uid),
        )
        conn.commit()
    return jsonify({"message": "Profile and settings saved."})


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
