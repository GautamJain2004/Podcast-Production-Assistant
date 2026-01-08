"""
Optional tiny CLI to run broker in foreground (useful for debug).
Example:
    python -m a2a_broker --pipeline refinement researcher outline script fact_validator show_notes social_media critic
"""
import argparse
import logging
import os
from .broker import get_global_broker

def main():
    parser = argparse.ArgumentParser(description="Run A2A broker (dev mode)")
    parser.add_argument("--pipeline", nargs="*", default=[], help="Ordered pipeline of agent topic names")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    broker = get_global_broker(pipeline_order=args.pipeline)
    broker.start_background_loop()
    print("A2A broker running (background loop). Press Ctrl-C to exit.")
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down broker...")
        broker.shutdown()

if __name__ == "__main__":
    main()
