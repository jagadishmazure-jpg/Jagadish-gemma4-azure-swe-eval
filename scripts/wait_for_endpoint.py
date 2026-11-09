"""Wait until an OpenAI-compatible endpoint answers /models (used by the cloud pipeline). Exit 1 after 15 min."""

import sys
import time
import urllib.request

url = sys.argv[1].rstrip("/") + "/models"
for _ in range(180):
    try:
        with urllib.request.urlopen(url, timeout=5):
            sys.exit(0)
    except OSError:
        time.sleep(5)
sys.exit(1)
