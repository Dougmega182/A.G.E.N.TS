import os
import sys
import json
from pathlib import Path
import asyncio

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.google_operator import GoogleOperator

async def test_recovery():
    print("--- STARTING GOOGLE AUTH RECOVERY TEST ---")
    
    # Define a test agent ID
    test_id = "recovery_test_agent"
    agent_dir = Path("agents") / test_id
    agent_dir.mkdir(parents=True, exist_ok=True)
    token_path = agent_dir / "token.json"
    
    # 1. Create a 0-byte token file
    print(f"[TEST] Creating 0-byte token at {token_path}...")
    with open(token_path, "w") as f:
        pass # Empty file
    
    operator = GoogleOperator(agent_id=test_id)
    
    print("[TEST] Calling authenticate()...")
    print("[TEST] NOTE: We expect it to fail gracefully (request browser) or catch the error, NOT a JSON decomposition crash.")
    
    try:
        # We don't want to actually open a browser in CI/test, 
        # but we want to see it catch the 0-byte file and attempt to proceed 
        # to the point where it would open the browser.
        
        # We'll mock InstalledAppFlow.from_client_secrets_file to prevent browser opening
        from unittest.mock import patch
        with patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file') as mock_flow:
            mock_flow.side_effect = Exception("INTERCEPTED_BROWSER_FLOW")
            
            try:
                operator.authenticate()
            except Exception as e:
                if "INTERCEPTED_BROWSER_FLOW" in str(e):
                    print("SUCCESS: JSON crash avoided. System attempted fresh auth flow.")
                else:
                    print(f"FAILED: Unexpected error during auth: {e}")
                    raise e
                    
        # Verify the 0-byte file was deleted
        if not token_path.exists():
            print("SUCCESS: 0-byte token file was successfully deleted by GoogleOperator.")
        else:
            print("FAILED: 0-byte token file still exists.")

    finally:
        # Cleanup
        if token_path.exists():
            token_path.unlink()
        if agent_dir.exists():
            agent_dir.rmdir()

if __name__ == "__main__":
    asyncio.run(test_recovery())
