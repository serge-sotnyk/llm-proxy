import asyncio
import time
import httpx
from fastapi import FastAPI, Request, HTTPException, Response
from typing import List

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import os
import sys

# Load configuration from .env file
API_KEYS = os.getenv("API_KEYS")
if not API_KEYS:
    sys.exit("Error: API_KEYS environment variable not set in .env. Please provide at least one API key separated by ';'.")
API_KEYS = API_KEYS.split(";")  # Expect semicolon-separated API keys

RATE_LIMIT = int(os.getenv("RATE_LIMIT", "15"))
TARGET_API_URL = os.getenv("TARGET_API_URL")
if not TARGET_API_URL:
    sys.exit("Error: TARGET_API_URL environment variable not set in .env. Please provide the target API URL.")

class APIKeyManager:
    """
    Class for managing API keys with a round-robin mechanism and rate limiting.
    For each key, statistics are kept in memory: the number of requests and the start time of the current window.
    """
    def __init__(self, api_keys: List[str], rate_limit: int, window: int = 60):
        self.api_keys = api_keys
        self.rate_limit = rate_limit
        self.window = window  # Window interval in seconds (60 seconds = 1 minute)
        self.lock = asyncio.Lock()
        # Initialize counter and window start time for each key
        self.stats = {key: {"count": 0, "window_start": time.time()} for key in api_keys}
        self.index = 0  # Current index for round-robin

    async def get_available_key(self) -> str:
        """
        Returns an available API key that has not exceeded the request limit.
        If the limit for the selected key is exhausted, tries the next ones.
        If all keys are exhausted, waits for the minimum wait time to expire.
        """
        async with self.lock:
            for _ in range(len(self.api_keys)):
                key = self.api_keys[self.index]
                stat = self.stats[key]
                current_time = time.time()
                # If the current window time has expired, reset the counter and update the window time
                if current_time - stat["window_start"] >= self.window:
                    stat["count"] = 0
                    stat["window_start"] = current_time
                # If the limit is not yet exhausted, use this key
                if stat["count"] < self.rate_limit:
                    stat["count"] += 1
                    # Update index for round-robin
                    self.index = (self.index + 1) % len(self.api_keys)
                    return key
                # Move to the next key
                self.index = (self.index + 1) % len(self.api_keys)
            # If all keys are exhausted, calculate the minimum wait time for the limit reset
            wait_times = []
            current_time = time.time()
            for key in self.api_keys:
                stat = self.stats[key]
                wait_time = self.window - (current_time - stat["window_start"])
                if wait_time < 0:
                    wait_time = 0
                wait_times.append(wait_time)
            min_wait = min(wait_times)
        # Wait for the required minimum time and retry
        await asyncio.sleep(min_wait)
        return await self.get_available_key()

# Initialize API key manager
key_manager = APIKeyManager(API_KEYS, RATE_LIMIT)

# Create FastAPI instance
app = FastAPI(title="Proxy API Gateway")

@app.api_route("/proxy/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(full_path: str, request: Request):
    # Get API key and form headers
    api_key = await key_manager.get_available_key()
    headers = dict(request.headers)
    headers["Authorization"] = f"Bearer {api_key}"

    # Read request body
    body = await request.body()

    # Form target API URL by adding the nested path
    target_url = f"{TARGET_API_URL}/{full_path}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=dict(request.query_params),
                content=body,
                timeout=180.0
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Error contacting the target API: {exc}") from exc

    return Response(content=response.content, status_code=response.status_code, headers=response.headers)

# Example of running the service:
# uvicorn proxy_app:app --host 0.0.0.0 --port 8000

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("proxy_app:app", host="0.0.0.0", port=8000, reload=True)