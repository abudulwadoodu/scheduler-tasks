
from app.db import SessionLocal
from app.models import Item, Source, Script

def dump_db():
    session = SessionLocal()
    with open("db_dump.txt", "w") as f:
        f.write("--- Sources ---\n")
        for s in session.query(Source).all():
            f.write(f"ID: {s.source_id}, Name: {s.source_name}\n")
            
        f.write("\n--- Scripts ---\n")
        for s in session.query(Script).all():
            f.write(f"ID: {s.id}, SourceID: {s.source_id}, Type: {s.type}, Path: {s.path}\n")
            
        f.write("\n--- Items ---\n")
        for i in session.query(Item).all():
            f.write(f"ID: {i.id}, Name: {i.name}, SourceID: {i.source_id}, ScriptID: {i.script_id}, ItemType: {i.item_type}, URL: {i.url}\n")
    session.close()

if __name__ == "__main__":
    dump_db()
