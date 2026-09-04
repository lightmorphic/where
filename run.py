"""Single runtime command: python run.py"""
from waitress import serve

from app import config, create_app

if __name__ == "__main__":
    serve(create_app(), host="0.0.0.0", port=config.PORT, threads=8)
