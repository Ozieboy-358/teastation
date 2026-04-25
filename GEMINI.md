***

# 🍵 TeaStation: System & Style Guide

## 1. Project Overview
TeaStation is a Flask-based "Brew Terminal" that integrates a traditional SQL database with a ChromaDB vector store for AI-driven recommendations. The inventory is managed via a `tea_station.yaml` file, which acts as the "Source of Truth" for tea profiles, brewing parameters, and pairings.

## 2. Inventory Architecture (`tea_station.yaml`)
Every tea in the system follows a specific schema defined in the YAML configuration:

* **Identifier**: The `container_name` or service key (e.g., `divine_intervention`).
* **Categories**: Defined types such as `Artisan`, `Energizer`, `Slenderizer`, `Relaxer`, `Immunity`, and `Seasonal`.
* **Brewing Parameters (Environment)**:
    * `RATIO`: Recommended leaf-to-water ratio (e.g., `1.5 tsp : 8oz`).
    * `TEMP`: Ideal water temperature (e.g., `175°F`).
    * `TIME`: Steeping duration in seconds (e.g., `240`).
* **Pairing Logic (Volumes)**:
    * **Additives**: Suggestions for sweeteners (rock sugar, honey), fruit infusions (lemon zest), and dairy (oat milk, coconut cream).
    * **Snacks**: Categorized into `Sweet` (shortbread, macarons) and `Savory` (smoked gouda, salted almonds).

## 3. Application Logic (`app.py`)
The Flask application bridges the gap between raw data and the user interface:

* **Database Syncing**: On startup, the system reads the YAML or SQL database to populate the ChromaDB vector store.
* **Vector Search**: The `ask_ai` route uses semantic search to find teas based on user vibes (e.g., "I need to focus on coding").
* **AI Sommelier**: Powered by a local `phi3` model, it returns a JSON response containing a `winner`, a `reason`, and a `vibe`.
* **Brew Tracking**: The system tracks `brew_count` for every tea to generate popularity statistics.

## 4. Design Guidelines
To maintain the "Tea Sommelier" persona, follow these conventions:

* **Tone**: Sophisticated, knowledgeable, and restorative.
* **Nomenclature**: Use descriptive titles (e.g., "The Gilded Teafling") rather than technical IDs.
* **Visuals**: Categories should be color-coded in the UI (e.g., Green for `Slenderizer`, Purple for `Relaxer`) to match the themes in the YAML.

## 5. Maintenance Commands
* **Syncing the Vault**: Run `sync_vault.py` or restart the app to refresh the vector database.
* **Exporting Data**: Use `tea_export.py` to backup current database states.
* **Stopping Services**: Use `stop_tea.ps1` to safely shut down the Flask and AI services.