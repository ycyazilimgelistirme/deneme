# Backend (Flask) - YCMuzic Professional
This backend provides:
- User auth (JWT) - demo only; replace password hashing with bcrypt in prod.
- Playlist CRUD synced to backend DB.
- Search & Track endpoints using YTMusicAPI with Redis caching (optional).
- Rate limiting via Flask-Limiter (supports Redis storage).

Configure via .env (see .env.example).
