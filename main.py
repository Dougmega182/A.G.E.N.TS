import uvicorn
import webbrowser
import threading
import time
from agents.api import app

def launch_browser():
    """Wait a second for the server to start, then open the UI."""
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000/static/index.html")

if __name__ == "__main__":
    # Move the web folder into a static directory for FastAPI to serve
    import os
    from fastapi.staticfiles import StaticFiles
    
    # Ensure static directory exists
    if not os.path.exists("static"):
        os.makedirs("static")
    
    # Copy index.html to static for serving
    if os.path.exists("web/index.html"):
        with open("web/index.html", "r", encoding="utf-8") as f:
            content = f.read()
        with open("static/index.html", "w", encoding="utf-8") as f:
            f.write(content)

    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    print("\n" + "="*50)
    print(" A.G.E.N.T.S. INTERACTIVE TERMINAL ")
    print("="*50)
    print("Backend: http://localhost:8000")
    print("Frontend: http://localhost:8000/static/index.html")
    print("="*50 + "\n")

    # Start browser in a background thread
    threading.Thread(target=launch_browser, daemon=True).start()

    # Launch FastAPI
    uvicorn.run(app, host="0.0.0.0", port=8000)
