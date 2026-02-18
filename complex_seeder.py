import pyodbc
import yaml
import json
from database.vectordb import VectorDB

def complex_seed():
    with open("settings.yaml", "r") as f:
        config = yaml.safe_load(f)

    conn_str = config.get("sql_connection_string")
    vdb = VectorDB()
    
    # 1. Diverse Data Definition
    data = [
        # Electronics (Source 1)
        (6, "Sony WH-1000XM5", 1, "Electronics", "Industry-leading noise canceling with Auto NC Optimizer."),
        (7, "Apple MacBook Pro", 1, "Electronics", "M3 Max chip, 14-inch Liquid Retina XDR display, 36GB RAM."),
        (8, "Samsung Galaxy S24", 1, "Electronics", "AI-powered smartphone with Quad Telephoto system."),
        
        # Grocery (Source 5)
        (9, "Organic Arabica Coffee", 5, "Grocery", "Whole bean dark roast coffee, 100% organic and fair trade."),
        (10, "Extra Virgin Olive Oil", 5, "Grocery", "Cold-pressed Italian olive oil, 500ml bottle."),
        (11, "Gluten-Free Oats", 5, "Grocery", "Steel-cut oats, fiber-rich and gluten-free certified."),
        
        # Home (Source 2)
        (12, "Ergonomic Office Chair", 2, "Home", "High-back mesh chair with lumbar support and adjustable armrests."),
        (13, "Memory Foam Mattress", 2, "Home", "Queen size pressure-relieving foam with cooling gel layer."),
        (14, "Smart LED Lamp", 2, "Home", "Dimmable desk lamp with wireless charging and voice control."),
        
        # Clothing (Source 3)
        (15, "Waterproof Winter Jacket", 3, "Clothing", "Insulated parka with fleece lining and detachable hood."),
        (16, "Running Shoes", 3, "Clothing", "Lightweight breathable mesh sneakers with responsive cushioning."),
        (17, "Unisex Cotton Hoodie", 3, "Clothing", "Heavyweight 100% cotton sweatshirt with kangaroo pocket.")
    ]

    print("--- Starting Complex Seeding ---")

    with pyodbc.connect(conn_str) as conn:
        cursor = conn.cursor()
        
        # 2. Cleanup embeddings (to avoid duplicates for these IDs)
        item_ids = [d[0] for d in data]
        id_str = ",".join(map(str, item_ids))
        cursor.execute(f"DELETE FROM dbo.item_embeddings WHERE item_id IN ({id_str})")
        
        # 3. Insert/Update items metadata
        print("Upserting item metadata...")
        for item_id, name, source_id, item_type, content in data:
            # Check if exists
            cursor.execute("SELECT id FROM dbo.items WHERE id = ?", (item_id,))
            if cursor.fetchone():
                cursor.execute(
                    "UPDATE dbo.items SET name = ?, source_id = ?, item_type = ?, description = ? WHERE id = ?",
                    (name, source_id, item_type, content, item_id)
                )
            else:
                # Using dummy values for required fields not provided in 'data'
                cursor.execute(
                    "INSERT INTO dbo.items (id, name, source_id, item_type, description, url, active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (item_id, name, source_id, item_type, content, f"https://example.com/p/{item_id}", 1)
                )
        conn.commit()

    # 4. Generate and store embeddings
    print("Generating embeddings...")
    for item_id, name, source_id, item_type, content in data:
        print(f"  Processing: {name}...")
        vdb.add_document(item_id, content)

    print("--- Seeding Complete ---")

if __name__ == "__main__":
    complex_seed()
