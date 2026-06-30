import json
import os
import random
import string
from datetime import datetime
from typing import Dict, List, Optional

DB_PATH = "data/db.json"

DEFAULT_DB = {
    "clients": {},
    "client_users": {},  # telegram_id -> client_name
    "access_codes": {},  # code -> client_name
    "payments": {},      # client_name -> list of payments
    "meta_dues": {},     # account_id -> due amount
    "alerts": {},        # client_name -> alert settings
    "settings": {
        "agency_name": "SKF Boosting",
        "agency_phone": "",
        "agency_whatsapp": "",
        "daily_report_time": "09:00",
        "alert_budget_threshold": 80,
    }
}


def load_db() -> dict:
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(DB_PATH):
        save_db(DEFAULT_DB)
        return DEFAULT_DB.copy()
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db: dict):
    os.makedirs("data", exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


# ─── CLIENT ───────────────────────────────────────────────

def get_all_clients() -> Dict:
    return load_db().get("clients", {})


def get_client(name: str) -> Optional[dict]:
    return load_db()["clients"].get(name)


def add_client(name: str, account_id: str, phone: str = "", whatsapp: str = "") -> bool:
    db = load_db()
    if name in db["clients"]:
        return False
    db["clients"][name] = {
        "account_id": account_id,
        "phone": phone,
        "whatsapp": whatsapp,
        "active": True,
        "telegram_id": None,
        "created_at": datetime.now().isoformat(),
    }
    db["payments"][name] = []
    save_db(db)
    return True


def update_client(name: str, **kwargs) -> bool:
    db = load_db()
    if name not in db["clients"]:
        return False
    db["clients"][name].update(kwargs)
    save_db(db)
    return True


def delete_client(name: str) -> bool:
    db = load_db()
    if name not in db["clients"]:
        return False
    del db["clients"][name]
    save_db(db)
    return True


def toggle_client(name: str) -> bool:
    db = load_db()
    if name not in db["clients"]:
        return False
    db["clients"][name]["active"] = not db["clients"][name]["active"]
    save_db(db)
    return db["clients"][name]["active"]


# ─── ACCESS CODE ──────────────────────────────────────────

def generate_access_code(client_name: str) -> str:
    db = load_db()
    code = "SKF-" + "".join(random.choices(string.digits, k=4))
    # remove old codes for this client
    db["access_codes"] = {
        k: v for k, v in db["access_codes"].items()
        if v["client_name"] != client_name
    }
    db["access_codes"][code] = {
        "client_name": client_name,
        "created_at": datetime.now().isoformat(),
        "used": False,
    }
    save_db(db)
    return code


def use_access_code(code: str, telegram_id: int) -> Optional[str]:
    db = load_db()
    entry = db["access_codes"].get(code)
    if not entry or entry["used"]:
        return None
    client_name = entry["client_name"]
    entry["used"] = True
    db["client_users"][str(telegram_id)] = client_name
    db["clients"][client_name]["telegram_id"] = telegram_id
    save_db(db)
    return client_name


def get_client_by_telegram(telegram_id: int) -> Optional[str]:
    db = load_db()
    return db["client_users"].get(str(telegram_id))


def revoke_client_access(client_name: str):
    db = load_db()
    tid = db["clients"].get(client_name, {}).get("telegram_id")
    if tid:
        db["client_users"].pop(str(tid), None)
        db["clients"][client_name]["telegram_id"] = None
    save_db(db)


# ─── PAYMENTS / DUE ───────────────────────────────────────

def add_payment(client_name: str, amount: float, note: str = "") -> bool:
    db = load_db()
    if client_name not in db["clients"]:
        return False
    db["payments"].setdefault(client_name, []).append({
        "amount": amount,
        "note": note,
        "date": datetime.now().isoformat(),
    })
    save_db(db)
    return True


def get_payments(client_name: str) -> List[dict]:
    return load_db().get("payments", {}).get(client_name, [])


def get_due_summary() -> List[dict]:
    db = load_db()
    result = []
    for name, info in db["clients"].items():
        payments = db.get("payments", {}).get(name, [])
        total_paid = sum(p["amount"] for p in payments)
        result.append({
            "name": name,
            "account_id": info["account_id"],
            "total_paid": total_paid,
            "active": info["active"],
        })
    return result


# ─── SETTINGS ─────────────────────────────────────────────

def get_settings() -> dict:
    return load_db().get("settings", DEFAULT_DB["settings"])


def update_settings(**kwargs):
    db = load_db()
    db["settings"].update(kwargs)
    save_db(db)


# ─── INVOICE COUNTER ──────────────────────────────────────

def next_invoice_number() -> str:
    db = load_db()
    count = db.get("invoice_count", 0) + 1
    db["invoice_count"] = count
    save_db(db)
    return f"INV-{datetime.now().year}-{count:04d}"
