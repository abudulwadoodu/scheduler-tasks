from database.vectordb import VectorDB
import time

def seed_and_simulate():
    vdb = VectorDB()
    
    print("--- [Seed] Adding Diverse Products ---")
    
    # Data mapping from db_dump.txt
    # 24: Amazon Product (Source 1, type_1)
    # 25: Flipkart Product (Source 2, type_1) 
    # 26: eBay Collectible (Source 3, type_1)
    # 27: Walmart Grocery (Source 5, type_1)
    # 28: Walmart Electronics (Source 5, type_2)
    
    products = [
        {
            "item_id": 1, 
            "content": "abcPulsar 150.",
            "label": "abcBajaj - Two Wheeler"
        },
        {
            "item_id": 2,
            "content": "abcActiva.",
            "label": "abcHonda - Two Wheeler"
        },
        {
            "item_id": 3, 
            "content": "abci10.",
            "label": "abcHyundai - Four Wheeler"
        },
        {
            "item_id": 4,
            "content": "abcJeep Compass.",
            "label": "abcJeep - Four Wheeler"
        },
        {
            "item_id": 5,
            "content": "abcBaleno",
            "label": "abcMaruti - Four Wheeler"
        }
    ]

    for p in products:
        print(f"Adding: {p['label']} (ID: {p['item_id']})")
        vdb.add_document(p['item_id'], p['label'])

    print("\n--- [Simulation] Filtered Similarity Search ---")

    def run_query(query, filters=None):
        filter_desc = f"Filters: {filters}" if filters else "No filters"
        print(f"\nQuery: '{query}' ({filter_desc})")
        results = vdb.similarity_search(query, top_k=3, filters=filters)
        if not results:
            print("No results found.")
            return
        for i, res in enumerate(results):
            print(f"{i+1}. [{res['source_name']}] {res['item_name']} (Dist: {res['distance']:.4f})")
            print(f"   Content: {res['content'][:80]}...")

    # Case 1: Search for electronics, no filters
    run_query("Show me bikes")

if __name__ == "__main__":
    seed_and_simulate()
