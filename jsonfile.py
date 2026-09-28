import json
import logging
import os
import threading
import time

REPLACE_ATTEMPTS = 10
RETRY_DELAY_SECONDS = 0.05

LOG = logging.getLogger(__name__)


def write_json_file(path, data, indent=None):
    """Write json to a unique temp file and swap it in, retrying blocked swaps."""
    temp_path = path.with_suffix(f".{os.getpid()}-{threading.get_ident()}.tmp")
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=indent, separators=None if indent else (",", ":"))
    if replace_with_retry(temp_path, path):
        return True
    LOG.warning("could not replace %s, keeping the previous file", path.name)
    remove_quietly(temp_path)
    return False


def replace_with_retry(temp_path, path):
    """Swap the temp file in, waiting out short locks by scanners or other processes."""
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(temp_path, path)
            return True
        except PermissionError:
            time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))
    return False


def remove_quietly(path):
    """Delete a file, ignoring a failure to do so."""
    try:
        os.remove(path)
    except OSError:
        pass
