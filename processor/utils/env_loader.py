# utils/env_loader.py
import os
import argparse
from dotenv import load_dotenv

def load_environment():
    """
    Parse command line for an --env argument and load environment variables.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=None, help="Path to .env file")
    args, _ = parser.parse_known_args()

    if args.env:
        if not os.path.exists(args.env):
            raise FileNotFoundError(f".env file not found at {args.env}")
        load_dotenv(dotenv_path=args.env)
    else:
        # In Docker, Compose env_file already injects env vars.
        # Locally, this will load .env from the current working directory if present.
        load_dotenv()

