from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from array import array
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence


MODEL_NAME = "local-hash-ngram-v1"
DIMENSIONS = 384


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(value).lower())
    without_accents = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    ).replace("đ", "d")
    return " ".join(re.findall(r"\w+", without_accents, flags=re.UNICODE))


def iter_features(text: str) -> Iterable[str]:
    normalized = normalize_text(text)
    words = re.findall(r"\w+", normalized, flags=re.UNICODE)
    for word in words:
        yield f"w:{word}"
        padded = f"^{word}$"
        for size in (3, 4, 5):
            if len(padded) < size:
                continue
            for index in range(len(padded) - size + 1):
                yield f"c{size}:{padded[index:index + size]}"

    for index in range(len(words) - 1):
        yield f"b:{words[index]}_{words[index + 1]}"


def _feature_slot(feature: str, dimensions: int) -> tuple[int, float]:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    raw_value = int.from_bytes(digest, byteorder="little", signed=False)
    slot = raw_value % dimensions
    sign = 1.0 if (raw_value >> 63) == 0 else -1.0
    return slot, sign


def embed_text(text: str, dimensions: int = DIMENSIONS) -> list[float]:
    vector = [0.0] * dimensions
    counts = Counter(iter_features(text))
    for feature, count in counts.items():
        slot, sign = _feature_slot(feature, dimensions)
        vector[slot] += sign * (1.0 + math.log(float(count)))

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude:
        vector = [value / magnitude for value in vector]
    return vector


def build_post_text(post: Mapping[str, Any]) -> str:
    title = str(post.get("title", ""))
    topic = str(post.get("topic", ""))
    tags = str(post.get("mock_tags", ""))
    summary = str(post.get("mock_summary", ""))
    content = str(post.get("content", ""))
    return "\n".join(
        [
            f"{title}\n{title}\n{title}",
            f"{topic}\n{topic}\n{topic}",
            f"{tags}\n{tags}\n{tags}",
            f"{summary}\n{summary}",
            content,
        ]
    )


def embed_post(post: Mapping[str, Any]) -> list[float]:
    return embed_text(build_post_text(post))


def serialize_vector(vector: Sequence[float]) -> bytes:
    values = array("f", (float(value) for value in vector))
    return values.tobytes()


def deserialize_vector(payload: bytes | bytearray | memoryview | None) -> list[float]:
    if payload is None:
        return []
    values = array("f")
    values.frombytes(bytes(payload))
    return values.tolist()


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return float(sum(a * b for a, b in zip(left, right)))

