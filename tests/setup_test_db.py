import sqlite3
import json
import os

def setup_test_db():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(base_dir)
    db_path = os.path.join(parent_dir, 'tea_station.db')
    json_path = os.path.join(base_dir, 'sample_teas.json')

    if os.path.exists(db_path):
        confirm = input(f"Database {db_path} already exists. Overwrite? (y/n): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table based on app.py schema
    cursor.execute('''
        CREATE TABLE tea (
            id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            category VARCHAR(50),
            notes TEXT,
            brew_count INTEGER DEFAULT 0,
            last_brewed DATETIME,
            temp VARCHAR(20),
            time INTEGER,
            ratio VARCHAR(50),
            additions VARCHAR(100),
            snack VARCHAR(100)
        )
    ''')

    with open(json_path, 'r', encoding='utf-8') as f:
        teas = json.load(f)

    for tea in teas:
        cursor.execute('''
            INSERT INTO tea (name, category, ratio, temp, time, additions, snack, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tea['name'], tea['category'], tea['ratio'], tea['temp'], tea['time'], tea['additions'], tea['snack'], tea['notes']))

    conn.commit()
    conn.close()
    print(f"✅ Successfully created test database at {db_path} with {len(teas)} sample teas.")

if __name__ == "__main__":
    setup_test_db()
