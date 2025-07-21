#!/usr/bin/env python3
"""
Debug runner for the FastAPI application.
This file is used for debugging purposes and runs the FastAPI app directly with uvicorn.
"""

import os
import sys
from pathlib import Path

# Add the src directory to Python path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

if __name__ == "__main__":
    import uvicorn
    from api.main import create_app
    
    # Load environment variables if not in production
    if not os.getenv("RUNNING_IN_PRODUCTION"):
        from dotenv import load_dotenv
        load_dotenv(override=True)
    
    app = create_app()
    
    # Run with uvicorn for debugging
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=50505,
        reload=True,
        log_level="debug"
    )
