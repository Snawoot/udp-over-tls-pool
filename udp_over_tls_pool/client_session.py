import asyncio
import logging


class ClientSession:
    def __init__(self, conn_factory, recv_cb, *, pool_size=8):
        self._conn_factory = conn_factory
        self._pool_size = pool_size
        self._session_id = uuid.uuid4().bytes
        self._queue = asyncio.Queue(128)
        self._conns = [conn_factory(self._session_id, recv_cb, self._queue)
                       for _ in range(pool_size)]

    async def stop(self):
        await asyncio.gather(*(conn.stop() for conn in self._conns))

    def enqueue(self, data):
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            pass
