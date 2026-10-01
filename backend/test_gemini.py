import asyncio
import httpx
from backend.config import settings

async def main():
    key = settings.GEMINI_API_KEY
    candidates = [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.7-flash",
        "gemini-3.8-flash",
        "gemini-flash-latest"
    ]
    async with httpx.AsyncClient(timeout=15.0) as client:
        for m in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
            body = {
                "contents": [{"parts": [{"text": "Return JSON: {\"status\": \"ok\"}"}]}],
                "generationConfig": {"responseMimeType": "application/json"}
            }
            try:
                resp = await client.post(url, json=body)
                print(f"Model {m}: Status {resp.status_code}")
                if resp.status_code == 200:
                    print("  SUCCESS! Output:", resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip())
                    return m
                else:
                    print(f"  Error: {resp.text[:120]}")
            except Exception as e:
                print(f"  Exception for {m}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
