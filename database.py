from app import db, app

def init_database():
    with app.app_context():
        db.create_all()
        print("Database initialized successfully")
