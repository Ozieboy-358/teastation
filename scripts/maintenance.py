import os
import shutil
import sqlite3
import time
import requests
from datetime import datetime, timedelta

# --- CONFIG ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')

DB_PATH = os.path.join(DATA_DIR, 'tea_station.db')
OLLAMA_URL = "http://localhost:11434/api/tags"

def run_maintenance():
    print(f"[{datetime.now()}] --- STARTING MAINTENANCE ---")

    # 1. DATABASE BACKUP
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"tea_station_{timestamp}.db")
    
    try:
        shutil.copy2(DB_PATH, backup_path)
        print(f"[OK] Database backed up to: {backup_path}")
    except Exception as e:
        print(f"[ERROR] Backup failed: {e}")

    # 2. LOG CLEANUP (Files older than 7 days)
    print("LOG CLEANUP: Cleaning up old logs...")
    now = time.time()
    for f in os.listdir(LOG_DIR):
        f_path = os.path.join(LOG_DIR, f)
        if os.stat(f_path).st_mtime < now - (7 * 86400):
            if os.path.isfile(f_path):
                os.remove(f_path)
                print(f"   Deleted: {f}")

    # 3. AI HEALTH CHECK
    print("AI HEALTH: Checking AI Health...")
    try:
        resp = requests.get(OLLAMA_URL, timeout=5)
        if resp.status_code == 200:
            models = [m['name'] for m in resp.json().get('models', [])]
            print(f"[OK] Ollama Online. Models available: {', '.join(models)}")
        else:
            print(f"[WARN] Ollama returned status: {resp.status_code}")
    except Exception as e:
        print(f"[ERROR] Ollama unreachable: {e}")

    # 4. BACKUP ROTATION (Keep only last 5 backups)
    backups = sorted([os.path.join(BACKUP_DIR, b) for b in os.listdir(BACKUP_DIR)], key=os.path.getmtime)
    while len(backups) > 5:
        old_b = backups.pop(0)
        os.remove(old_b)
        print(f"ROTATION: Deleted old backup: {os.path.basename(old_b)}")

    print(f"[{datetime.now()}] --- MAINTENANCE COMPLETE ---")

if __name__ == "__main__":
    run_maintenance()
