import asyncio
import os
from dotenv import load_dotenv

import redis.asyncio as redis

load_dotenv()

async def check_redis():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    print(f"Checking Redis connection at: {redis_url}")
    
    try:
        # Create a connection client
        client = redis.from_url(redis_url)
        # Ping the server
        response = await client.ping()
        if response:
            print("✅ SUCCESS: Redis is connected and running!")
        else:
            print("❌ ERROR: Redis ping returned unexpected response.")
    except Exception as e:
        print(f"❌ ERROR: Could not connect to Redis.")
        print(f"Details: {e}")
        print("\nMake sure Redis is installed and running on your machine!")
    finally:
        try:
            await client.aclose()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(check_redis())
