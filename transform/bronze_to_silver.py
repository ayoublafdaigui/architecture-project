"""Compatibility entrypoint for the MediaPulse Bronze to Silver pipeline."""

from mediapulse.transform.bronze_to_silver import *  # noqa: F401,F403
from mediapulse.transform.bronze_to_silver import main


if __name__ == "__main__":
    main()
