
from app.db import SessionLocal
from app.models import Source, Script

def check_structure():
    session = SessionLocal()
    print("\n--- Sources ---")
    sources = session.query(Source).all()
    for s in sources:
        print(f"ID: {s.source_id}, Name: {s.source_name}")

    print("\n--- Scripts ---")
    scripts = session.query(Script).all()
    for s in scripts:
        print(f"ID: {s.id}, SourceID: {s.source_id}, Type: {s.type}, Path: {s.path}")
    session.close()

if __name__ == "__main__":
    check_structure()
