from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from blueprints import openaicall
import asyncio

def create_app():
    app = FastAPI()
    app.config = {
        "SECRET_KEY": "prod",
        "JSON_AS_ASCII": False
    }

    # Register routers (previously blueprints)
    app.include_router(openaicall.router)

    # Setup CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Specify domains
        allow_credentials=True,
        allow_methods=["*"],  # Specify methods
        allow_headers=["*"],  # Specify headers
    )

    return app

if __name__ == "__main__":
    app = create_app()