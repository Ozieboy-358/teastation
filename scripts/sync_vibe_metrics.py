import sqlite3
import os

db_path = os.path.join('data', 'tea_station.db')

def analyze_and_sync():
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, category, notes FROM tea")
    teas = cursor.fetchall()

    # Enhanced Keyword maps
    keywords = {
        'focus': ['focus', 'study', 'work', 'clarity', 'alert', 'sharp', 'bright', 'morning', 'clean', 'grassy', 'pine'],
        'relaxation': ['relax', 'sleep', 'calm', 'night', 'evening', 'gentle', 'soft', 'smooth', 'herbal', 'floral', 'chamomile', 'lavender', 'honey', 'sweet'],
        'energy': ['energy', 'caffeine', 'bold', 'intense', 'strong', 'kick', 'awake', 'black', 'chai', 'pu-erh', 'dark', 'robust', 'spicy'],
        'complexity': ['complex', 'layers', 'lingering', 'artisanal', 'notes of', 'profile', 'finish', 'delicate', 'smoky', 'charred', 'oak', 'oil-slick', 'tobacco', 'cacao', 'roasted', 'malt', 'earthy']
    }

    print(f"Recalculating vibe metrics for {len(teas)} teas...")

    for tea in teas:
        metrics = {'focus': 5, 'relaxation': 5, 'energy': 5, 'complexity': 5}
        notes = (tea['notes'] or "").lower()
        cat = (tea['category'] or "").lower()
        full_text = f"{notes} {cat}"

        for m in metrics:
            score = 5
            for word in keywords[m]:
                if word in full_text:
                    score += 2 # Increased weight for keyword matches
            metrics[m] = min(10, round(score))

        # Fine-tune logic
        if 'black tea' in full_text or 'pu-erh' in full_text or 'chai' in full_text:
            metrics['energy'] = max(metrics['energy'], 8)
            metrics['relaxation'] = min(metrics['relaxation'], 5)
        
        if 'herbal' in full_text or 'fruit' in full_text or 'decaf' in full_text:
            metrics['relaxation'] = max(metrics['relaxation'], 8)
            metrics['energy'] = min(metrics['energy'], 4)

        if 'oil-slick' in full_text or 'smoky' in full_text:
            metrics['complexity'] = 10
            metrics['energy'] = max(metrics['energy'], 9)

        cursor.execute("""
            UPDATE tea 
            SET focus = ?, relaxation = ?, energy = ?, complexity = ?
            WHERE id = ?
        """, (metrics['focus'], metrics['relaxation'], metrics['energy'], metrics['complexity'], tea['id']))

    conn.commit()
    conn.close()
    print("Vibe Radar values updated successfully.")

if __name__ == "__main__":
    analyze_and_sync()
