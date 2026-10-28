import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import app
import httpx

async def main():
    print("[TEST] Running real server stream for SC-004 with provider=baseten...")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        async with client.stream("GET", "/api/stream/SC-004?provider=baseten") as response:
            print(f"[TEST] Response status: {response.status_code}")
            async for line in response.aiter_lines():
                if line.startswith("event:") or line.startswith("data:"):
                    print(line)

if __name__ == "__main__":
    asyncio.run(main())
