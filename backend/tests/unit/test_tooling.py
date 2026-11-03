"""Sample tests: make sure that async tests and Hypothesis tests run."""

import anyio
import pytest
from hypothesis import given
from hypothesis import strategies as st


@pytest.mark.anyio
async def test_async_test_runs() -> None:
    send, receive = anyio.create_memory_object_stream[int](1)
    async with send, receive:
        await send.send(1)
        assert await receive.receive() == 1


@given(st.lists(st.integers()))
def test_hypothesis_test_runs(values: list[int]) -> None:
    assert list(reversed(list(reversed(values)))) == values
