"""Compatibility entrypoint for the MediaPulse Silver to Gold pipeline."""

from mediapulse.transform.silver_to_gold import *  # noqa: F401,F403
from mediapulse.transform.silver_to_gold import main


if __name__ == "__main__":
    main()
