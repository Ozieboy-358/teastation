import sqlite3
import os

db_path = os.path.join('data', 'tea_station.db')

def patch():
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    new_columns = [
        ('focus', 'INTEGER DEFAULT 5'),
        ('relaxation', 'INTEGER DEFAULT 5'),
        ('energy', 'INTEGER DEFAULT 5'),
        ('complexity', 'INTEGER DEFAULT 5')
    ]

    for col_name, col_type in new_columns:
        try:
            print(f"Adding column {col_name}...")
            cursor.execute(f"ALTER TABLE tea ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists.")
            else:
                print(f"Error adding column {col_name}: {e}")
    
    conn.commit()
    conn.close()
    print("Database patched successfully.")

if __name__ == "__main__":
    patch()
