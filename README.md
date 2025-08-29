# YCMuzic — Professional Edition (Skeleton)

Bu depo, **tam profesyonel** sürüme giden kapsamlı bir iskelet sağlar:
- Backend: Flask + SQLAlchemy + JWT auth + playlists + caching (Redis optional) + rate-limiting
- Frontend: Next.js (React) responsive dark theme skeleton with pages and components
- Infra: Dockerfiles + docker-compose + Procfile for Render/Heroku-like deploys

NOT: Bu paket bir "tam" prod uygulamaya başlamak için hazırlanmış kapsamlı bir iskelet sunar. Güvenlik (şifre hashing, HTTPS, CORS detayları), ölçekleme, veri migrasyonları ve testler için ek çalışmalar gerekir.

## Hızlı Başlangıç (lokal)
1. Backend:
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env  # düzenle
   python app.py
   ```
2. Frontend (dev):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Önerilen Üretim Adımları
- Parola saklama için bcrypt entegrasyonu
- HTTPS ve reverse-proxy (nginx)
- Rate limit ve cache için Redis
- CI/CD pipeline (GitHub Actions)
- Unit & integration tests
