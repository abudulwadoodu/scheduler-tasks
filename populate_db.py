import os
import re
from scheduler_core.db import SessionLocal
from scheduler_core.models import Source, Script, Item, Schedule
from datetime import datetime, timezone, timedelta

def populate():
    session = SessionLocal()
    try:
        # 1. Create a default schedule
        now = datetime.now(timezone.utc)
        default_sched = Schedule(
            name="Default 30s Schedule",
            frequency_type="SECONDS",
            interval_value=30,
            active=True,
            next_run_time=now
        )
        session.add(default_sched)
        session.flush()
        sched_id = default_sched.id
        print(f"Created default schedule with ID: {sched_id}")

        with open("db_dump.txt", "r") as f:
            content = f.read()

        # 2. Parse Sources
        sources_section = re.search(r"--- Sources ---(.*?)--- Scripts ---", content, re.DOTALL)
        if sources_section:
            source_lines = sources_section.group(1).strip().split("\n")
            for line in source_lines:
                if not line.strip(): continue
                # ID: 1, Name: Amazon
                match = re.search(r"ID: (\d+), Name: (.*)", line)
                if match:
                    s_id, s_name = match.groups()
                    source = Source(
                        source_id=int(s_id),
                        source_name=s_name,
                        source_type="E-Commerce",
                        active=True,
                        schedule_id=sched_id
                    )
                    session.add(source)
            print("Parsed and added Sources.")

        # 3. Parse Scripts
        scripts_section = re.search(r"--- Scripts ---(.*?)--- Items ---", content, re.DOTALL)
        if scripts_section:
            script_lines = scripts_section.group(1).strip().split("\n")
            for line in script_lines:
                if not line.strip(): continue
                # ID: 1, SourceID: 1, Type: type_1, Path: extractor_modules\amazon_type_1.py
                match = re.search(r"ID: (\d+), SourceID: (\d+), Type: (.*?), Path: (.*)", line)
                if match:
                    id, src_id, s_type, s_path = match.groups()
                    script = Script(
                        id=int(id),
                        source_id=int(src_id),
                        type=s_type,
                        path=s_path
                    )
                    session.add(script)
            print("Parsed and added Scripts.")

        # 4. Parse Items
        items_section = re.search(r"--- Items ---(.*)", content, re.DOTALL)
        if items_section:
            item_lines = items_section.group(1).strip().split("\n")
            for line in item_lines:
                if not line.strip(): continue
                # ID: 1, Name: HttpBin, SourceID: None, ScriptID: None, ItemType: None, URL: https://httpbin.org/get
                # Regex to handle ID, Name, SourceID, ScriptID, ItemType, URL
                match = re.search(r"ID: (\d+), Name: (.*?), SourceID: (.*?), ScriptID: (.*?), ItemType: (.*?), URL: (.*)", line)
                if match:
                    id, name, src_id, scr_id, i_type, url = match.groups()
                    
                    source_id = int(src_id) if src_id != "None" else None
                    script_id = int(scr_id) if scr_id != "None" else None
                    item_type = i_type if i_type != "None" else None
                    
                    item = Item(
                        id=int(id),
                        name=name,
                        source_id=source_id,
                        script_id=script_id,
                        item_type=item_type,
                        url=url,
                        schedule_id=sched_id,
                        status="PENDING",
                        active=True
                    )
                    session.add(item)
            print("Parsed and added Items.")

        session.commit()
        print("Database population completed successfully.")

    except Exception as e:
        session.rollback()
        print(f"Error populating database: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    populate()
