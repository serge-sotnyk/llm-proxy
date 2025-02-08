# FastAPI Proxy Application

This is a Python‑based proxy gateway application built with FastAPI. The application forwards incoming HTTP requests to a target API (e.g., Google Gemini API) and rotates through a list of API keys using a round‑robin scheme, while enforcing a rate limit of 15 requests per minute per API key.

## Features

- Accepts multiple HTTP methods on the `/proxy` endpoint.
- Uses an asynchronous HTTP client (httpx) for making requests to the target API.
- Implements an in‑memory rate limiting mechanism for each API key.
- Provides round‑robin API key rotation to distribute load evenly.
- Returns the response’s status code, headers, and body from the target API.

## Running the Application

To start the proxy service, run the following command:

```bash
uvicorn proxy_app:app --host 0.0.0.0 --port 8000
```

The proxy listens on port 8000. Send your HTTP requests to `http://localhost:8000/proxy`.

## Configuration

To configure the proxy application, you need to set the following environment variables. It is recommended to use a `.env` file in the same directory as `proxy_app.py` for easy configuration.

- **API_KEYS**: A semicolon-separated list of API keys. Example: `API_KEYS=key1;key2;key3`. At least one API key is required.
- **TARGET_API_URL**: The URL of the target API to which requests will be forwarded. Example: `TARGET_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent`. This variable is required.
- **RATE_LIMIT** (optional): The number of requests allowed per minute per API key. Defaults to `15` if not set. Example: `RATE_LIMIT=30`.

Example `.env` file:
```
API_KEYS=your_api_key_1;your_api_key_2
TARGET_API_URL=https://your-target-api.com/api
RATE_LIMIT=20
```

The application loads these environment variables at startup.

- To adjust the rate limiting settings, modify the `RATE_LIMIT` environment variable in your `.env` file.