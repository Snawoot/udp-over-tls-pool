import asyncio
import logging
import uuid

from .constants import MAX_DGRAM_QLEN


class ClientSession:
    def __init__(self, conn_factory, recv_cb, *, pool_size=8):
        self._session_id = uuid.uuid4()
        self._queue = asyncio.Queue(MAX_DGRAM_QLEN)
        self._conns = [conn_factory(self._session_id, recv_cb, self._queue)
                       for _ in range(pool_size)]
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Session with ID=%s started", self._session_id.hex)

    async def stop(self):
        await asyncio.gather(*(conn.stop() for conn in self._conns))
        self._logger.info("Session with ID=%s stopped", self._session_id.hex)

    def enqueue(self, data):
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            self._logger.warning("Session[%s]: queue full",
                                 self._session_id.hex)
