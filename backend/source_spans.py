"""Versioned, deterministic slices of immutable captures; no text normalization."""
import hashlib
from uuid import uuid5

SPAN_VERSION = "source-span-v1"
SPAN_SIZE = 1200
MODEL_CHAR_LIMIT = 30000


def source_spans(fetch):
    if hashlib.sha256(fetch.content.encode()).hexdigest() != fetch.content_hash:
        raise ValueError("Source capture hash mismatch")
    return [{"id": str(uuid5(fetch.id, f"{SPAN_VERSION}:{fetch.content_hash}:{start}")),
             "index": index, "start": start, "end": min(start + SPAN_SIZE, len(fetch.content)),
             "text": fetch.content[start:start + SPAN_SIZE]}
            for index, start in enumerate(range(0, len(fetch.content), SPAN_SIZE))]
