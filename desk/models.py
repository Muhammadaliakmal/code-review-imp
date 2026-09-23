from dataclasses import dataclass


@dataclass
class DiffChunk:
    file: str
    patch: str
