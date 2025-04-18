#!/usr/bin/env python3
"""Download required spaCy models for entity extraction."""

import subprocess
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

MODELS = [
    "en_core_web_sm",  # Small English model (efficient but less accurate)
    "en_core_web_md",  # Medium English model (balance between size and accuracy)
]

def download_spacy_models():
    """Download spaCy models."""
    logger.info("Starting spaCy model download")
    
    for model in MODELS:
        try:
            logger.info(f"Downloading model: {model}")
            subprocess.check_call([sys.executable, "-m", "spacy", "download", model])
            logger.info(f"Successfully downloaded model: {model}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to download model {model}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error downloading model {model}: {e}")
    
    logger.info("Finished downloading spaCy models")

if __name__ == "__main__":
    download_spacy_models() 