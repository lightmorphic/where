"""Single runtime command: python run.py"""
from waitress import serve

from app import bootstrap, config, create_app

if __name__ == "__main__":
    # Sort the data folder out and stop being root, before anything else.
    bootstrap.log_line(bootstrap.prepare(config.DATA_DIR))
    serve(create_app(), host="0.0.0.0", port=config.PORT, threads=8)
