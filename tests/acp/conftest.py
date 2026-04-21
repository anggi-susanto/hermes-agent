import asyncio

import pytest


@pytest.fixture(autouse=True)
def _cleanup_stray_event_loop():
    yield

    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
    except RuntimeError:
        loop = None

    if loop is None or loop.is_closed() or loop.is_running():
        return

    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.run_until_complete(loop.shutdown_default_executor())
    loop.close()

    try:
        asyncio.set_event_loop(None)
    except Exception:
        pass
