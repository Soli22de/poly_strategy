from pathlib import Path
from typing import List


def read_recent_lines(path: Path, max_lines: int = 50000, chunk_size: int = 1024 * 1024) -> List[str]:
    if max_lines < 1:
        raise ValueError("max_lines must be at least 1")
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if not path.exists() or path.stat().st_size == 0:
        return []

    chunks = []
    line_count = 0
    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        while position > 0 and line_count <= max_lines:
            read_size = min(chunk_size, position)
            position -= read_size
            handle.seek(position)
            data = handle.read(read_size)
            chunks.append(data)
            line_count += data.count(b"\n")

    data = b"".join(reversed(chunks))
    lines = data.splitlines()[-max_lines:]
    return [line.decode("utf-8", errors="replace") for line in lines if line.strip()]
