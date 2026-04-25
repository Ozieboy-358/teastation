from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import requests
import json
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
import os
import time
import gc

# --- 1. CONFIGURATION & ENV SETUP ---
load_dotenv()

# Get the absolute path of the project directory
project_dir = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# Use the existing database in the data directory
db_path = os.path.join(project_dir, 'data', 'tea_station.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY not set in environment variables.")

OPENWEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

db = SQLAlchemy(app)

# --- CACHING LAYER ---
AI_CACHE = {}

# --- GLOBAL DEFAULTS ---
DEFAULT_CATEGORIES = [
    'Black Tea', 'Green Tea', 'Herbal Tea', 'Oolong Tea', 'White Tea', 'Chai', 'Pu-erh'
]

# --- 2. VECTOR DATABASE ---
instance_path = os.path.join(project_dir, 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)
chroma_db_path = os.path.join(instance_path, "tea_vector_db")

_chroma_collection = None

def get_collection():
    """Lazy loader for ChromaDB collection to save resources on startup."""
    global _chroma_collection
    if _chroma_collection is None:
        import chromadb
        from chromadb.utils import embedding_functions
        client = chromadb.PersistentClient(path=chroma_db_path)
        emb_fn = embedding_functions.DefaultEmbeddingFunction()
        _chroma_collection = client.get_or_create_collection(name="tea_vault", embedding_function=emb_fn)
    return _chroma_collection

def retrieve_and_evaluate(query, n_results=10, is_late=False, user_input=""):
    """
    Dynamic Retrieval Strategy:
    1. Retrieve n_results candidates.
    2. Score based on distance, keyword match, and vibe alignment.
    3. Filter out fundamental mismatches.
    """
    collection = get_collection()
    results = collection.query(query_texts=[query], n_results=n_results)
    
    docs = results['documents'][0]
    metas = results['metadatas'][0]
    distances = results['distances'][0]
    
    scored_candidates = []
    
    # Keyword maps for re-ranking
    RELAX_KEYWORDS = ['sleep', 'relax', 'calm', 'night', 'evening', 'herbal', 'caffeine-free']
    ENERGY_KEYWORDS = ['focus', 'energy', 'morning', 'caffeine', 'work', 'study']
    
    user_input_lower = user_input.lower()
    needs_relax = any(k in user_input_lower for k in RELAX_KEYWORDS) or is_late
    needs_energy = any(k in user_input_lower for k in ENERGY_KEYWORDS)
    
    for doc, meta, dist in zip(docs, metas, distances):
        # Base score (lower distance is better, so we invert it)
        # Assuming dist is usually between 0 and 2
        score = (2.0 - dist) * 10 
        
        rel_val = meta.get('relaxation', 5)
        en_val = meta.get('energy', 5)
        
        # Hard filters/penalties
        if needs_relax:
            if en_val > 7: score -= 15 # Heavy penalty for high energy teas when relaxing
            if rel_val > 7: score += 10 # Bonus for relaxing teas
        
        if needs_energy:
            if en_val > 7: score += 10 # Bonus for energy teas
            if rel_val > 7: score -= 5 # Slight penalty for too relaxing teas
            
        # Keyword matching in doc
        for k in RELAX_KEYWORDS + ENERGY_KEYWORDS:
            if k in doc.lower():
                if (needs_relax and k in RELAX_KEYWORDS) or (needs_energy and k in ENERGY_KEYWORDS):
                    score += 5
                    
        scored_candidates.append({
            "doc": doc,
            "meta": meta,
            "score": score
        })
        
    # Sort by score descending
    scored_candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # Return top 5
    final_docs = [c['doc'] for c in scored_candidates[:5]]
    final_metas = [c['meta'] for c in scored_candidates[:5]]
    
    return final_docs, final_metas

# --- 3. SQL MODEL ---
class Tea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(db.String(50), default="Other")
    notes = db.Column(db.Text, nullable=True)
    brew_count = db.Column(db.Integer, default=0)
    last_brewed = db.Column(db.DateTime, nullable=True)
    temp = db.Column(db.String(20), default="212°F")
    time = db.Column(db.Integer, default=180)
    ratio = db.Column(db.String(50), default="1 tsp")
    additions = db.Column(db.String(100), default="None")
    snack = db.Column(db.String(100), default="None")
    # New metrics for Radar Chart
    focus = db.Column(db.Integer, default=5)
    relaxation = db.Column(db.Integer, default=5)
    energy = db.Column(db.Integer, default=5)
    complexity = db.Column(db.Integer, default=5)

# --- 4. MAIN NAVIGATION ROUTES ---
@app.route('/')
def index():
    """Home page: Brew Terminal and AI Sommelier."""
    teas = db.session.execute(db.select(Tea).order_by(Tea.name)).scalars().all()
    stats = db.session.execute(db.select(Tea).order_by(Tea.last_brewed.desc()).limit(10)).scalars().all()
    return render_template('index.html', teas=teas, stats=stats)

@app.route('/stats')
def stats():
    """Stats page: Displays tea rankings and collection charts."""
    all_teas = db.session.execute(db.select(Tea).order_by(Tea.brew_count.desc())).scalars().all()
    return render_template('stats.html', teas=all_teas)

@app.route('/graph')
def graph():
    """Graphs page: Displays visualizations and vibe analysis."""
    teas = db.session.execute(db.select(Tea).order_by(Tea.name)).scalars().all()
    return render_template('graph.html', teas=teas)

@app.route('/api/tea_data')
def api_tea_data():
    """Returns tea data with enhanced clustering coordinates based on categories and vibe metrics."""
    all_teas = db.session.execute(db.select(Tea)).scalars().all()
    
    # Get embeddings from Chroma
    ids = [str(t.id) for t in all_teas]
    if not ids:
        return jsonify([])
        
    results = get_collection().get(ids=ids, include=['embeddings'])
    
    # Categorical Centroids for tight clustering
    # Each category gets an orbital slot (angle)
    categories = sorted(list(set([t.category for t in all_teas])))
    cat_centers = {}
    import math
    for i, cat in enumerate(categories):
        angle = (i / len(categories)) * 2 * math.pi
        # Orbit radius for the centers
        radius = 0.6 
        cat_centers[cat] = {
            "x": math.cos(angle) * radius,
            "y": math.sin(angle) * radius
        }

    tea_map = []
    for t in all_teas:
        center = cat_centers.get(t.category, {"x": 0, "y": 0})
        
        # Jitter/Offset based on vibe metrics to separate teas within the same cluster
        # Normalize metrics to -0.1 to 0.1 range
        off_x = (t.energy - t.relaxation) / 50.0 # Energy pulls one way, Relaxation the other
        off_y = (t.focus - t.complexity) / 50.0  # Focus pulls one way, Complexity the other
        
        # Incorporate a tiny bit of embedding noise to ensure unique spots
        idx = -1
        try:
            idx = results['ids'].index(str(t.id))
            emb_noise_x = results['embeddings'][idx][0] * 0.05
            emb_noise_y = results['embeddings'][idx][1] * 0.05
        except:
            emb_noise_x = 0
            emb_noise_y = 0
            
        tea_map.append({
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "brew_count": t.brew_count,
            "focus": t.focus,
            "relaxation": t.relaxation,
            "energy": t.energy,
            "complexity": t.complexity,
            "x": center["x"] + off_x + emb_noise_x,
            "y": center["y"] + off_y + emb_noise_y
        })
        
    return jsonify(tea_map)

@app.route('/admin')
@app.route('/admin/edit/<int:id>')
def admin(id=None):
    """Admin page for CRUD operations and editing."""
    edit_tea = db.session.get(Tea, id) if id else None
    all_teas = db.session.execute(db.select(Tea).order_by(Tea.name)).scalars().all()
    raw = db.session.execute(db.select(Tea.category).distinct()).scalars().all()
    cat_map = {c.strip().lower(): c.strip() for c in raw if c and c.strip()}
    categories = sorted(cat_map.values(), key=str.lower)
    if not categories:
        categories = DEFAULT_CATEGORIES
    return render_template('admin.html', teas=all_teas, edit_tea=edit_tea, categories=categories)

# --- 5. API & LOGIC ROUTES ---
@app.route('/semantic_search', methods=['POST'])
def semantic_search():
    """Finds teas based on flavor/notes similarity."""
    query = request.json.get('query', '').strip()
    if not query:
        return jsonify([])
    results = get_collection().query(query_texts=[query], n_results=5)
    matches = []
    if results.get('metadatas') and results['metadatas'][0]:
        for meta in results['metadatas'][0]:
            matches.append({"name": meta['name']})
    return jsonify(matches)

@app.route('/get_weather', methods=['POST'])
def get_weather():
    if not OPENWEATHER_API_KEY:
        return jsonify({"error": "Server Configuration Error: API Key missing"}), 500
    data = request.json
    lat, lon = data.get('lat'), data.get('lon')
    if not lat or not lon:
        return jsonify({"error": "Coordinates missing"}), 400
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=imperial"
        response = requests.get(url)
        response.raise_for_status()
        weather_data = response.json()
        temp = round(weather_data['main']['temp'])
        desc = weather_data['weather'][0]['description'].title()
        return jsonify({"summary": f"Current weather: {desc}, {temp}°F", "temp": f"{temp}°F"})
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to fetch weather data: {e}"}), 500

@app.route('/ask_ai', methods=['POST'])
def ask_ai():
    data = request.json
    user_input = data.get('user_input', '').strip().lower()
    use_iced = data.get('use_iced', False)
    use_time = data.get('use_time', False) # New flag from frontend
    gaming_mode = data.get('gaming_mode', False)
    
    if 'ai_history' not in session:
        session['ai_history'] = []
    
    cache_key = f"{user_input}_iced:{use_iced}_time:{use_time}_gaming:{gaming_mode}"
    if cache_key in AI_CACHE:
        res = AI_CACHE[cache_key].copy()
        res["timings"] = {"retrieval": 0, "inference": 0, "total": 0, "cached": True}
        return jsonify(res)

    try:
        start_time = time.time()
        retrieval_start = time.time()
        
        # 1. Dynamic Retrieval based on user vibe and time
        current_hour = datetime.now().hour
        is_late = (current_hour >= 20 or current_hour < 5) and use_time
        
        # We retrieve more candidates and filter them for relevance
        unique_docs, unique_metas = retrieve_and_evaluate(user_input, n_results=10, is_late=is_late, user_input=user_input)
        
        inventory_context = "\n".join(unique_docs)
        pool_metas = unique_metas 

        if is_late:
            system_instruction = (
                "You are the Tea Terminal Sommelier. It is LATE NIGHT. "
                "You MUST recommend a CAFFEINE-FREE or HERBAL tea. "
                "DO NOT suggest Black, Green, or Oolong teas."
            )
        elif "relax" in user_input or "sleep" in user_input:
            system_instruction = "You are the Tea Terminal Sommelier. Prioritize relaxing, caffeine-free teas."
        else:
            system_instruction = "You are the Tea Terminal Sommelier. Recommend the best tea from the INVENTORY."

        retrieval_time = round((time.time() - retrieval_start) * 1000)

        if use_iced:
            system_instruction += (
                " The user wants an ICED TEA. Choose a tea that is refreshing or flavor-stable when cold (e.g., fruit-forward, hibiscus, or robust blacks). "
            )
        
        system_instruction += (
            " Use ONLY the exact 'Tea Name' provided in the INVENTORY list below. "
            "DO NOT add any suffixes like '(INVENTORY)' or extra descriptions to the tea name in the 'winner' field. "
            "If no perfect match exists, pick the most relevant one from the provided list."
        )

        prompt = f"""
        [SYSTEM]
        {system_instruction}
        
        [INVENTORY]
        {inventory_context}
        
        [CURRENT REQUEST]
        "{user_input}"
        
        Return JSON with keys: "winner", "reason", "vibe".
        """
        
        inference_start = time.time()
        
        # Ollama payload
        ollama_payload = {
            "model": "phi3.5", 
            "prompt": prompt, 
            "format": "json", 
            "stream": False,
            "keep_alive": 0
        }
        
        # If gaming mode is ON, force CPU by setting num_gpu to 0
        if gaming_mode:
            ollama_payload["options"] = {"num_gpu": 0}

        response = requests.post('http://localhost:11434/api/generate',
                                 json=ollama_payload,
                                 timeout=60) # Increased timeout for CPU inference
        response.raise_for_status()
        inference_time = round((time.time() - inference_start) * 1000)
        
        raw_response = response.json().get('response', '{}').strip()
        # Strip markdown code blocks if present
        if raw_response.startswith("```"):
            raw_response = raw_response.split("\n", 1)[-1]
            if raw_response.endswith("```"):
                raw_response = raw_response.rsplit("\n", 1)[0]
        
        ai_data = json.loads(raw_response)
        winner_name = ai_data.get('winner', '')
        # Try exact match first, then fallback to partial
        chosen = db.session.execute(db.select(Tea).filter(Tea.name == winner_name)).scalars().first()
        if not chosen and winner_name:
            chosen = db.session.execute(db.select(Tea).filter(Tea.name.ilike(f"%{winner_name}%"))).scalars().first()
        
        # Build similar teas from the pool, excluding the winner
        similar_teas = []
        winner_actual_name = chosen.name if chosen else winner_name
        for meta in pool_metas:
            if meta['name'] != winner_actual_name:
                similar_teas.append({"name": meta['name']})

        session['ai_history'].append({"u": user_input, "a": ai_data.get('reason')})
        session.modified = True

        result_payload = {
            "recommendation": chosen.name if chosen else winner_name,
            "reason": ai_data.get('reason', 'Analysis complete.'),
            "vibe": ai_data.get('vibe', 'Neutral'),
            "similar_teas": similar_teas,
            "timings": {"retrieval": retrieval_time, "inference": inference_time, "total": round((time.time() - start_time) * 1000), "cached": False}
        }
        AI_CACHE[cache_key] = result_payload
        
        # Explicitly trigger garbage collection after heavy inference
        gc.collect()
        
        return jsonify(result_payload)
    except Exception as e:
        return jsonify({"recommendation": "Error", "reason": f"Sommelier Logic Error: {e}"}), 500

@app.route('/admin/save', methods=['POST'])
@app.route('/admin/save/<int:id>', methods=['POST'])
def save_tea(id=None):
    if id:
        tea = db.session.get(Tea, id)
        if not tea:
            flash("Tea not found!")
            return redirect(url_for('admin'))
    else:
        tea = Tea()
        db.session.add(tea)
    tea.name = request.form['name']
    tea.category = (request.form.get('new_category') or 'Other').strip() if request.form.get('category') == 'NEW' else request.form.get('category')
    tea.temp = request.form.get('temp')
    tea.time = int(request.form.get('time', 0))
    tea.ratio = request.form.get('ratio')
    tea.additions = request.form.get('additions')
    tea.snack = request.form.get('snack')
    tea.notes = request.form.get('notes')
    tea.focus = int(request.form.get('focus', 5))
    tea.relaxation = int(request.form.get('relaxation', 5))
    tea.energy = int(request.form.get('energy', 5))
    tea.complexity = int(request.form.get('complexity', 5))
    db.session.commit()
    
    detail_doc = (
        f"Tea Name: {tea.name}. "
        f"Category: {tea.category}. "
        f"Flavor Profile: {tea.notes}. "
        f"Recommended Additions: {tea.additions}. "
        f"Best Snack Pairing: {tea.snack}. "
        f"Brewing Specs: {tea.temp} for {tea.time} seconds."
    )
    get_collection().upsert(ids=[str(tea.id)], documents=[detail_doc], metadatas=[{"name": tea.name, "id": str(tea.id)}])
    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:id>', methods=['POST'])
def delete_tea(id):
    tea = db.session.get(Tea, id)
    if tea:
        db.session.delete(tea)
        db.session.commit()
        try: get_collection().delete(ids=[str(id)])
        except: pass
    return redirect(url_for('admin'))

@app.route('/get_tea/<name>')
def get_tea(name):
    tea = db.session.execute(db.select(Tea).filter(Tea.name.ilike(name.strip()))).scalar_one_or_none()
    if tea:
        return jsonify({"name": tea.name, "category": tea.category, "temp": tea.temp, "time": tea.time, "ratio": tea.ratio, "additions": tea.additions, "snack": tea.snack, "notes": tea.notes, "brew_count": tea.brew_count})
    return jsonify({"error": "Tea not found"}), 404

@app.route('/increment_brew/<name>', methods=['POST'])
def increment_brew(name):
    tea = db.session.execute(db.select(Tea).filter(Tea.name.ilike(name.strip()))).scalar_one_or_none()
    if tea:
        tea.brew_count += 1
        tea.last_brewed = datetime.now()
        db.session.commit()
        stats = db.session.execute(db.select(Tea).order_by(Tea.last_brewed.desc()).limit(10)).scalars().all()
        stats_data = [{"name": t.name, "brew_count": t.brew_count} for t in stats]
        return jsonify({"success": True, "new_count": tea.brew_count, "stats": stats_data})
    return jsonify({"success": False, "error": "Tea not found"}), 404

def sync_vector_db():
    with app.app_context():
        all_teas = db.session.execute(db.select(Tea)).scalars().all()
        if not all_teas: return
        
        ids = []
        docs = []
        metas = []
        
        for t in all_teas:
            ids.append(str(t.id))
            detail_doc = (
                f"Tea Name: {t.name}. "
                f"Category: {t.category}. "
                f"Vibe Metrics - Focus: {t.focus}, Relaxation: {t.relaxation}, Energy: {t.energy}, Complexity: {t.complexity}. "
                f"Flavor Profile: {t.notes}. "
                f"Recommended Additions: {t.additions}. "
                f"Best Snack Pairing: {t.snack}. "
                f"Brewing Specs: {t.temp} for {t.time} seconds."
            )
            docs.append(detail_doc)
            metas.append({"name": t.name, "category": t.category, "relaxation": t.relaxation, "energy": t.energy})
            
        get_collection().upsert(ids=ids, documents=docs, metadatas=metas)

def init_db():
    with app.app_context(): 
        db.create_all()
    
    # Run maintenance on startup
    try:
        import subprocess
        maint_path = os.path.join(project_dir, 'scripts', 'maintenance.py')
        subprocess.Popen(['C:\\Users\\oswal\\AppData\\Local\\Programs\\Python\\Python311\\python.exe', maint_path])
    except:
        pass

if __name__ == '__main__':
    init_db()
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true": sync_vector_db()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
