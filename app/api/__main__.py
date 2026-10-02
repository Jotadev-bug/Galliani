"""Run the API and web UI: python -m app.api [--host 127.0.0.1] [--port 8000]"""

import argparse

import uvicorn


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1", help="keep localhost until auth and rate limiting exist")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true")
    args = p.parse_args()
    uvicorn.run("app.api.routes:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
