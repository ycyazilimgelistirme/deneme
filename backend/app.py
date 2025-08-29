import os, logging, json, time
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
from ytmusicapi import YTMusic
import redis

# Config
BASE_DIR = os.path.dirname(__file__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ytmusic-professional")

app = Flask(__name__, static_folder="../frontend/.next", static_url_path="/")
CORS(app)

# Load env-like config
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', f"sqlite:///{os.path.join(BASE_DIR,'data.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'jwt-secret')
app.config['PLAYER_MODE'] = os.getenv('PLAYER_MODE', 'EMBED').upper()
REDIS_URL = os.getenv('REDIS_URL', None)
RATE_LIMIT = os.getenv('RATE_LIMIT', "200 per day;50 per hour")

db = SQLAlchemy(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

# Optional Redis for caching and rate limiting storage
redis_client = None
if REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        logger.warning("Redis init failed: %s", e)
        redis_client = None

# Rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[RATE_LIMIT], storage_uri=REDIS_URL or "memory://")

ytmusic = None
try:
    ytmusic = YTMusic(region=os.getenv('YT_REGION') or None)
except Exception as e:
    logger.exception("YTMusic init failed")

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), unique=True, nullable=False)
    display_name = db.Column(db.String(128))
    password_hash = db.Column(db.String(256))  # in production use proper hashing (bcrypt)

class Playlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    items = db.Column(db.Text)  # JSON list of tracks
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.Float, default=lambda: time.time())

# DB helper
def init_db():
    db.create_all()

@app.route("/api/health")
def health():
    return jsonify({"status":"ok"})

# Auth endpoints (simple email+password demo)
@app.route("/api/auth/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error":"email and password required"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error":"user exists"}), 400
    # NOTE: Use bcrypt in production
    user = User(email=email, display_name=email.split("@")[0], password_hash=password)
    db.session.add(user); db.session.commit()
    access = create_access_token(identity=user.id)
    return jsonify({"access_token": access, "user": {"id": user.id, "email": user.email, "display_name": user.display_name}})

@app.route("/api/auth/login", methods=["POST"])
@limiter.limit("20 per hour")
def login():
    data = request.get_json() or {}
    email = data.get("email"); password = data.get("password")
    user = User.query.filter_by(email=email).first()
    if not user or user.password_hash != password:
        return jsonify({"error":"invalid credentials"}), 401
    token = create_access_token(identity=user.id)
    return jsonify({"access_token": token, "user": {"id": user.id, "email": user.email, "display_name": user.display_name}})

# Playlist endpoints (authenticated)
@app.route("/api/playlists", methods=["GET","POST"])
@jwt_required(optional=True)
def playlists():
    current = get_jwt_identity()
    if request.method == "GET":
        if current:
            pls = Playlist.query.filter_by(user_id=current).all()
            return jsonify([{"id":p.id,"name":p.name,"items": json.loads(p.items or "[]")} for p in pls])
        else:
            return jsonify([])
    else:
        data = request.get_json() or {}
        name = data.get("name","Yeni Liste")
        items = data.get("items", [])
        p = Playlist(user_id=current or 0, name=name, items=json.dumps(items))
        db.session.add(p); db.session.commit()
        return jsonify({"id": p.id, "name": p.name, "items": items})

@app.route("/api/playlists/<int:pl_id>", methods=["PUT","DELETE"])
@jwt_required()
def modify_playlist(pl_id):
    current = get_jwt_identity()
    pl = Playlist.query.get_or_404(pl_id)
    if pl.user_id != current:
        return jsonify({"error":"permission denied"}), 403
    if request.method == "PUT":
        data = request.get_json() or {}
        pl.name = data.get("name", pl.name)
        pl.items = json.dumps(data.get("items", json.loads(pl.items or "[]")))
        db.session.commit()
        return jsonify({"id": pl.id, "name": pl.name, "items": json.loads(pl.items)})
    else:
        db.session.delete(pl); db.session.commit()
        return jsonify({"ok": True})

# Search and track endpoints with caching
def cache_get(key):
    if redis_client:
        try: return redis_client.get(key)
        except: return None
    return None

def cache_set(key, value, ex=300):
    if redis_client:
        try: redis_client.set(key, value, ex=ex); return True
        except: return False
    return False

@app.route("/api/search")
@limiter.limit("60 per minute")
def api_search():
    q = request.args.get("q","").strip()
    if not q:
        return jsonify({"error":"q required"}), 400
    key = f"search:{q.lower()}"
    cached = cache_get(key)
    if cached:
        return jsonify(json.loads(cached))
    if not ytmusic:
        return jsonify({"error":"YTMusic unavailable"}), 500
    try:
        results = ytmusic.search(q, filter="songs", limit=36)
        items = []
        for r in results:
            if not r.get("videoId"): continue
            thumbs = r.get("thumbnails") or []
            thumb = thumbs[-1]["url"] if thumbs else None
            artists = ", ".join([a.get("name","") for a in (r.get("artists") or []) if a.get("name")])
            items.append({"videoId": r.get("videoId"), "title": r.get("title"), "artists": artists, "duration": r.get("duration"), "thumbnail": thumb})
        payload = {"items": items}
        cache_set(key, json.dumps(payload), ex=300)
        return jsonify(payload)
    except Exception as e:
        logger.exception("search failed")
        return jsonify({"error": str(e)}), 500

@app.route("/api/track/<video_id>")
@limiter.limit("120 per minute")
def api_track(video_id):
    key = f"track:{video_id}"
    cached = cache_get(key)
    if cached: return jsonify(json.loads(cached))
    if not ytmusic: return jsonify({"error":"YTMusic unavailable"}), 500
    try:
        info = ytmusic.get_song(video_id)
        # normalize
        video = info.get("videoDetails", {})
        micro = info.get("microformat", {}).get("microformatDataRenderer", {})
        thumbs = micro.get("thumbnail", {}).get("thumbnails", []) or []
        thumb = thumbs[-1]["url"] if thumbs else video.get("thumbnail")
        details = {
            "videoId": video.get("videoId"),
            "title": video.get("title"),
            "author": video.get("author"),
            "publishDate": micro.get("publishDate"),
            "viewCount": video.get("viewCount"),
            "lengthSeconds": video.get("lengthSeconds"),
            "shortDescription": micro.get("description") if isinstance(micro.get("description"), str) else video.get("shortDescription"),
            "thumbnail": thumb
        }
        # related
        related = []
        watch = ytmusic.get_watch_playlist(videoId=video_id)
        for t in (watch.get("tracks") or [])[:40]:
            thumbs = t.get("thumbnails") or []
            rthumb = thumbs[-1]["url"] if thumbs else None
            related.append({"videoId": t.get("videoId"), "title": t.get("title"), "artists": ", ".join([a.get("name","") for a in (t.get("artists") or []) if a.get("name")]), "duration": t.get("duration"), "thumbnail": rthumb})
        payload = {"details": details, "related": related}
        cache_set(key, json.dumps(payload), ex=600)
        return jsonify(payload)
    except Exception as e:
        logger.exception("track failed")
        return jsonify({"error": str(e)}), 500

# Serve frontend files (if built)
@app.route("/", defaults={"path":""})
@app.route("/<path:path>")
def serve(path):
    # If frontend is built and files exist, serve them; otherwise simple message
    index_path = os.path.join(BASE_DIR, "../frontend/out/index.html")
    if os.path.exists(index_path):
        try:
            return send_from_directory(os.path.join(BASE_DIR, "../frontend/out"), path or "index.html")
        except Exception:
            return send_from_directory(os.path.join(BASE_DIR, "../frontend/out"), "index.html")
    return jsonify({"message":"Backend running. Build the frontend and place into frontend/out to serve static."})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=(os.getenv("FLASK_ENV","development")!="production"))
