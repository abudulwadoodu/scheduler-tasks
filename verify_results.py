from database.vectordb import VectorDB

def verify_filters():
    vdb = VectorDB()
    
    scenarios = [
        ("Baleno qwe", {}),
        ("qwe Maruti", {}),
        ("Balenoqwe", {}),
        ("qweMaruti", {}),
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
