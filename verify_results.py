from database.vectordb import VectorDB

def verify_filters():
    vdb = VectorDB()
    
    scenarios = [
        ("Query: 'Show me bikes' - Filter: Two Wheeler", {"item_type": "Two Wheeler"}),
        ("Query: 'Show me cars' - Filter: Four Wheeler", {"item_type": "Four Wheeler"}),
        ("Query: 'Looking for caffeine' - Filter: Grocery", {"item_type": "Grocery"}),
        ("Query: 'Comfortable office chair' - Filter: Home", {"item_type": "Home"}),
        ("Query: 'Warm winter wear' - Filter: Clothing", {"item_type": "Clothing"})
    ]

    for desc, filters in scenarios:
        print(f"\n>>> {desc}")
        results = vdb.similarity_search(desc, top_k=3, filters=filters)
        if not results:
            print("   (No matching items found)")
            continue
        for i, res in enumerate(results):
            print(f"   {i+1}. [{res['source_name']}] {res['item_name']} - Dist: {res['distance']:.4f}")
            print(f"      {res['content'][:60]}...")

if __name__ == "__main__":
    verify_filters()
