# SPDX-License-Identifier: Apache-2.0
"""Byte views over LMCache ``MemoryObj`` buffers.

Shared by the in-process connector and the MP-mode L2 adapter. It imports
nothing from LMCache, so neither adapter has to import the other to reach it.
"""

from __future__ import annotations

from typing import Any


def byte_view(memory_obj: Any) -> memoryview:
    """Return a flat unsigned-byte view over a ``MemoryObj`` buffer."""

    buffer = memory_obj.byte_array
    view = buffer if isinstance(buffer, memoryview) else memoryview(buffer)
    if view.format != "B":
        view = view.cast("B")
    return view
