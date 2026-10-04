import logging
import sys

from web.server import MathToolsServer


def run_server() -> None:
    """Serve the web dashboard."""
    MathToolsServer().run_server()


def main() -> None:
    """Entry point of the `mathtools` command: serve the web dashboard."""
    try:
        run_server()
    except Exception as exc:
        logging.error("Unexpected error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
