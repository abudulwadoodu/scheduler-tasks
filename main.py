from database.vectordb import VectorDB

def main():
    """
    Main execution script to demonstrate vector similarity search.
    """
    try:
        print("--- Initializing Vector Similarity System ---")
        vdb = VectorDB()

        # 1. Add a sample document
        print("\n[Step 1] Adding a document...")
        # Assuming item_id 24 exists (from db_dump.txt)
        item_id = 24 
        content = "This is a product description about high-performance laptops with solid-state drives and 16GB RAM."
        vdb.add_document(item_id, content)
        print("Document added successfully.")

        # 2. Perform a similarity search
        print("\n[Step 2] Performing similarity search...")
        query = "Show me laptops with 16GB RAM"
        results = vdb.similarity_search(query, top_k=3)

        print(f"Top results for query: '{query}':")
        for i, res in enumerate(results):
            print(f"{i+1}. Item: {res['item_name']} (Source: {res['source_name']})")
            print(f"   Content: {res['content'][:100]}...")
            print(f"   Distance: {res['distance']:.4f}")

        # 3. Perform a filtered similarity search
        print("\n[Step 3] Performing filtered similarity search (Amazon only)...")
        filters = {"source_id": 1} # Amazon source_id from db_dump.txt
        filtered_results = vdb.similarity_search(query, top_k=3, filters=filters)

        print(f"Filtered results for query: '{query}':")
        for i, res in enumerate(filtered_results):
            print(f"{i+1}. Item: {res['item_name']} (Source: {res['source_name']})")
            print(f"   Distance: {res['distance']:.4f}")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
