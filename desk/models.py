from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel


@dataclass
class DiffChunk:
    file: str
    patch: str


class Finding(BaseModel):
    file: str
    line: int
    severity: Literal["critical", "major", "minor"]
    message: str
