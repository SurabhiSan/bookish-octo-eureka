from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChunkNode:
    content: str
    chunk_index: int
    parent_index: Optional[int] = None
    keywords: list[str] = field(default_factory=list)
    micro_summary: str = ""


def chunk_document(text: str, source_type: str) -> list[ChunkNode]:
    if source_type == "tweet" or len(text) < 500:
        return [ChunkNode(content=text, chunk_index=0)]

    if source_type == "transcript":
        return _chunk_transcript(text)

    return _hierarchical_chunk(text)


def _chunk_transcript(text: str) -> list[ChunkNode]:
    lines = text.strip().split("\n")
    segments, current, idx = [], [], 0
    for line in lines:
        current.append(line)
        approx_tokens = sum(len(l.split()) for l in current) * 1.3
        if approx_tokens >= 400:
            segments.append(ChunkNode(content="\n".join(current), chunk_index=idx))
            current, idx = [], idx + 1
    if current:
        segments.append(ChunkNode(content="\n".join(current), chunk_index=idx))
    return segments


def _hierarchical_chunk(text: str) -> list[ChunkNode]:
    words = text.split()
    leaf_size, parent_size = 256, 1024  # tokens ≈ words * 0.75 for rough estimate
    leaf_words, parent_words = int(leaf_size / 0.75), int(parent_size / 0.75)

    chunks, idx = [], 0
    parent_idx = None

    # Create parent chunks
    parent_starts = list(range(0, len(words), parent_words))
    parents = []
    for ps in parent_starts:
        parent_content = " ".join(words[ps: ps + parent_words])
        parent_node = ChunkNode(content=parent_content, chunk_index=idx)
        parents.append((idx, ps))
        chunks.append(parent_node)
        idx += 1

    # Create leaf chunks under each parent
    for parent_i, (parent_chunk_idx, parent_start) in enumerate(parents):
        end = parents[parent_i + 1][1] if parent_i + 1 < len(parents) else len(words)
        leaf_starts = list(range(parent_start, end, leaf_words))
        for ls in leaf_starts:
            leaf_content = " ".join(words[ls: ls + leaf_words])
            chunks.append(ChunkNode(
                content=leaf_content,
                chunk_index=idx,
                parent_index=parent_chunk_idx,
            ))
            idx += 1

    return chunks
