
from app.db import SessionLocal
from app.models import Item, Source, Script

def check_items():
    session = SessionLocal()
    items = session.query(Item).all()
    print(f"Total items found: {len(items)}")
    for i in items:
        source_name = "None"
        if i.source_id:
            source = session.query(Source).filter(Source.source_id == i.source_id).first()
            source_name = source.source_name if source else "Unknown"
        
        script_path = "None"
        if i.script_id:
            script = session.query(Script).filter(Script.id == i.script_id).first()
            script_path = script.path if script else "Unknown"
            
        print(f"ID: {i.id}, Name: {i.name}, Source: {source_name}, Script: {script_path}")
    session.close()

if __name__ == "__main__":
    check_items()
