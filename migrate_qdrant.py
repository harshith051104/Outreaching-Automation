import os
import sys
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

COLLECTIONS = ["campaigns", "leads", "emails", "replies", "signals", "company_research"]

def main():
    print("=== Qdrant Database Migration Script ===")
    print("This script migrates your local Qdrant collections to Qdrant Cloud.\n")

    # 1. Source configuration
    print("Select local source type:")
    print("1) Running Local Qdrant Server (http://localhost:6333)")
    print("2) Local File-based Storage (./storage/qdrant_local)")
    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        source_url = input("Enter local server URL [http://localhost:6333]: ").strip() or "http://localhost:6333"
        print(f"Connecting to local Qdrant server at {source_url}...")
        try:
            source_client = QdrantClient(url=source_url, timeout=5.0)
            source_client.get_collections()
        except Exception as e:
            print(f"Error: Could not connect to local server: {e}")
            sys.exit(1)
    elif choice == "2":
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage", "qdrant_local")
        if not os.path.exists(local_path):
            print(f"Error: Local storage directory not found at '{local_path}'.")
            sys.exit(1)
        print(f"Opening local file-based database at {local_path}...")
        try:
            source_client = QdrantClient(path=local_path)
        except Exception as e:
            print(f"Error: Could not open local database: {e}")
            sys.exit(1)
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)

    # 2. Target configuration
    target_url = input("\nEnter your target Qdrant Cloud URL (e.g. https://xxx.qdrant.tech): ").strip()
    if not target_url:
        print("Error: Target URL is required.")
        sys.exit(1)
    target_api_key = input("Enter your target Qdrant Cloud API Key: ").strip()
    if not target_api_key:
        print("Error: Target API key is required.")
        sys.exit(1)

    print(f"\nConnecting to Qdrant Cloud target at {target_url}...")
    try:
        target_client = QdrantClient(url=target_url, api_key=target_api_key, timeout=10.0)
        target_client.get_collections()
    except Exception as e:
        print(f"Error: Could not connect to target Qdrant Cloud: {e}")
        sys.exit(1)

    # 3. Migrate collections
    print("\nStarting migration...")
    source_collections = [c.name for c in source_client.get_collections().collections]
    
    for col in COLLECTIONS:
        if col not in source_collections:
            print(f"Collection '{col}' does not exist on source – skipping.")
            continue
            
        print(f"\nMigrating collection: '{col}'...")

        # Get point count
        try:
            collection_info = source_client.get_collection(col)
            points_count = collection_info.points_count
            print(f"Found {points_count} points in collection '{col}'.")
        except Exception as e:
            print(f"Error reading collection '{col}' info: {e}")
            continue

        if points_count == 0:
            print(f"Collection '{col}' is empty – skipping point transfer.")
            continue

        # Create target collection
        try:
            target_collections = [c.name for c in target_client.get_collections().collections]
            if col not in target_collections:
                print(f"Creating collection '{col}' on target (384 dimensions, COSINE distance)...")
                target_client.create_collection(
                    collection_name=col,
                    vectors_config=VectorParams(
                        size=384,
                        distance=Distance.COSINE
                    )
                )
            else:
                print(f"Collection '{col}' already exists on target.")
        except Exception as e:
            print(f"Error creating collection '{col}' on target: {e}")
            continue

        # Scroll and upsert points in batches
        print("Transferring points...")
        offset = None
        limit = 100
        transferred = 0

        while True:
            try:
                scroll_res = source_client.scroll(
                    collection_name=col,
                    limit=limit,
                    with_payload=True,
                    with_vectors=True,
                    offset=offset
                )
                points, offset = scroll_res
                
                if not points:
                    break

                # Convert Record elements to PointStruct explicitly
                from qdrant_client.http.models import PointStruct
                point_structs = [
                    PointStruct(
                        id=p.id,
                        vector=p.vector,
                        payload=p.payload
                    )
                    for p in points
                ]

                # Upsert points to target
                target_client.upsert(
                    collection_name=col,
                    points=point_structs
                )
                
                transferred += len(points)
                print(f"  Transferred {transferred}/{points_count} points...")

                if offset is None:
                    break
            except Exception as e:
                print(f"Error transferring batch for '{col}': {e}")
                break

        print(f"Successfully migrated collection '{col}'!")

    print("\n=== Migration Completed Successfully! ===")

if __name__ == "__main__":
    main()
