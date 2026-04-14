import asyncio
import os
from dotenv import load_dotenv
from agents.llm import LLMProvider

async def debug_llm():
    load_dotenv()
    llm = LLMProvider()
    print(f"DEBUG: Provider={llm.provider}, Model={llm.model}")
    
    print("Testing astream_chat...")
    try:
        tokens = []
        async for token in llm.astream_chat("You are a helpful assistant.", "Say hello"):
            print(f"TOKEN: '{token}'")
            tokens.append(token)
        
        if not tokens:
            print("ERROR: No tokens yielded.")
        else:
            print(f"SUCCESS: Received {len(tokens)} tokens.")
            
    except Exception as e:
        print(f"EXCEPTION: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_llm())
