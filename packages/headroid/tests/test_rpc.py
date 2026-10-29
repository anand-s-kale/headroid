# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
import pytest

from headroid.rpc import RpcClient, RpcError


def test_call_roundtrip(fake_server):
    c = RpcClient("127.0.0.1", fake_server.port)
    assert c.call("echo", a=1, b="x") == {"a": 1, "b": "x"}
    assert c.events == [{"type": "x"}]
    c.close()


def test_error_raises_rpcerror(fake_server):
    c = RpcClient("127.0.0.1", fake_server.port)
    with pytest.raises(RpcError) as ei:
        c.call("boom")
    assert ei.value.code == -32010
    c.close()
