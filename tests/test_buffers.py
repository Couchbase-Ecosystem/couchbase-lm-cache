# SPDX-License-Identifier: Apache-2.0

import array
from types import SimpleNamespace

from couchbase_lm_cache._buffers import byte_view


def test_byte_view_flattens_typed_buffers_to_bytes():
    floats = array.array("f", [1.0, 2.0])
    view = byte_view(SimpleNamespace(byte_array=memoryview(floats)))

    assert view.format == "B"
    assert view.nbytes == len(view) == floats.itemsize * 2
    assert bytes(view) == floats.tobytes()


def test_byte_view_writes_through_to_the_buffer():
    buffer = bytearray(4)
    byte_view(SimpleNamespace(byte_array=buffer))[:] = b"abcd"

    assert buffer == b"abcd"
