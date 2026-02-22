import asyncio
from app.services.gemini import gemini_service

async def test_gemini():
    print("Testing Gemini connection...")
    try:
        response = await gemini_service.generate_json("""
        [
            "Buy milk",
            "Build Viyugam"
        ]
        """)
        print("Success! Response from Gemini:")
        print(response)
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
