import sys
import os
# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, Tea, get_collection

def sync_now():
    with app.app_context():
        # Ensure the database tables exist
        db.create_all()

        # Query all teas from your specific 'tea' table
        teas = Tea.query.all()
        print(f"🔄 Syncing {len(teas)} teas from tea_station.db to Vector Vault...")

        ids = []
        docs = []
        metas = []

        for tea in teas:
            ids.append(str(tea.id))

            # Creating a highly detailed document for the AI to "understand" your specific blends
            # This includes the category, notes, and even the snack pairings found in your DB
            detail_doc = (
                f"Tea Name: {tea.name}. "
                f"Category: {tea.category}. "
                f"Vibe Metrics - Focus: {tea.focus}, Relaxation: {tea.relaxation}, Energy: {tea.energy}, Complexity: {tea.complexity}. "
                f"Flavor Profile: {tea.notes}. "
                f"Recommended Additions: {tea.additions}. "
                f"Best Snack Pairing: {tea.snack}. "
                f"Brewing Specs: {tea.temp} for {tea.time} seconds."
            )

            docs.append(detail_doc)
            metas.append({"name": tea.name, "category": tea.category, "relaxation": tea.relaxation, "energy": tea.energy})

        if ids:
            # Clear old data and upload the new database contents
            get_collection().upsert(ids=ids, documents=docs, metadatas=metas)
            print("✅ Vector Vault Synchronized with your custom database.")
        else:
            print("⚠️ No teas found in the database. Check if data/tea_station.db is in the project folder.")

if __name__ == "__main__":
    sync_now()