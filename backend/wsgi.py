from app import create_app  # Eğer app/__init__.py içinde create_app fonksiyonu varsa

app = create_app()

if __name__ == "__main__":
    app.run()
