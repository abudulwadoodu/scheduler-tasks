
import os
import re
from datetime import datetime, timezone
from app.db import SessionLocal
from app.models import Item, Source, Script

def populate_mappings():
    session = SessionLocal()
    extractor_dir = "extractor_modules"
    
    if not os.path.exists(extractor_dir):
        print(f"Directory {extractor_dir} not found.")
        return

    # 1. Scan extractor_modules for scripts
    files = [f for f in os.listdir(extractor_dir) if f.endswith(".py") and "_" in f]
    
    for filename in files:
        # Expected format: source_type.py (e.g., amazon_type_1.py)
        match = re.match(r"^([a-zA-Z0-9]+)_(.+)\.py$", filename)
        if not match:
            continue
            
        source_name_raw = match.group(1)
        item_type = match.group(2)
        
        # Check if Source exists (Do NOT create)
        source = session.query(Source).filter(Source.source_name.ilike(source_name_raw)).first()
        if not source:
            print(f"Source '{source_name_raw}' not found in database. Skipping script '{filename}'.")
            continue
            
        # Ensure Script exists
        script_path = os.path.join(extractor_dir, filename)
        script = session.query(Script).filter(Script.path == script_path).first()
        if not script:
            print(f"Creating script entry for: {filename}")
            script = Script(
                source_id=source.source_id,
                type=item_type,
                path=script_path
            )
            session.add(script)
            session.flush()

    # 2. Map Scripts to Items based on manual source_id and item_type
    print("Mapping scripts to items based on manual source_id and item_type...")
    
    # Get all scripts for lookup
    all_scripts = session.query(Script).all()
    script_map = {(s.source_id, s.type): s.id for s in all_scripts}
    
    items = session.query(Item).all()
    for item in items:
        if item.source_id and item.item_type:
            # Look for a matching script
            script_id = script_map.get((item.source_id, item.item_type))
            if script_id:
                if item.script_id != script_id:
                    print(f"  Mapping item {item.id} ({item.name}) to script ID {script_id}")
                    item.script_id = script_id
            else:
                # Check for a 'default' script for that source
                default_script_id = script_map.get((item.source_id, "default"))
                if default_script_id and item.script_id != default_script_id:
                    print(f"  Mapping item {item.id} ({item.name}) to default script for source {item.source_id}")
                    item.script_id = default_script_id

    session.commit()
    session.close()
    print("Population and mapping complete.")

if __name__ == "__main__":
    populate_mappings()
