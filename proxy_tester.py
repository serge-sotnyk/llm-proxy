import asyncio
import os
import json
from openai import AsyncOpenAI


def print_full_response(response):
    try:
        print(json.dumps(response, indent=2, ensure_ascii=False))
    except Exception:
        from pprint import pprint
        pprint(response)


async def test_api(base_url: str, api_key: str):
    # For direct API calls, we need a valid key; for proxy, the proxy uses its own.
    client = AsyncOpenAI(api_key=api_key, base_url=base_url)
    try:
        response = await client.chat.completions.create(
            model="models/gemini-2.0-flash-exp",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ],
            temperature=0.5,
            timeout=60,
        )
        print(f"Response from API at {base_url}:")
        print_full_response(response)
    except Exception as e:
        print(f"Error calling API at {base_url}: {e}")


async def main():
    if not(api_key := os.environ.get("GEMINI_API_KEY")):
        print("GEMINI_API_KEY is not set in the environment.")
        return

    # Test direct API call using the real GEMINI_API_KEY
    direct_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    await test_api(direct_url, api_key)

    # Test call through the local proxy
    proxy_url = "http://127.0.0.1:8000"
    await test_api(proxy_url, api_key)


if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()
    asyncio.run(main())
