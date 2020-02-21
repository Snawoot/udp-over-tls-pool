import asyncio
import logging
from .constants import MAX_DGRAM_QLEN

class DgramUpstream:
    _loop = None
    _transport = None
    _started = False
    _done = None
    _queue = None

    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._logger = logging.getLogger(self.__class__.__name__)

    async def start(self):
        self._loop = asyncio.get_event_loop()
        self._done = self._loop.create_future()
        self._queue = asyncio.Queue(MAX_DGRAM_QLEN)
        self._transport, _ = await self._loop.create_datagram_endpoint(
            lambda: self, remote_addr=(self._host, self._port))
        self._started = True
        self._logger.info("UDP session to %s started", (self._host, self._port))

    async def stop(self):
        self._started = False
        self._transport.close()
        await self._done
        self._logger.info("UDP session to %s stopped", (self._host, self._port))

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.stop()

    def connection_made(self, transport):
        pass

    def connection_lost(self, transport):
        self._done.set_result(True)

    def datagram_received(self, data, addr):
        try:
            self._queue.put_nowait(data)
        except asyncio.QueueFull:
            self._logger.warning("UDP session %s: receive queue full",
                                 repr((self._host, self._port)),
                                 self._session_id.hex)

    def write(self, data):
        self._transport.sendto(data)

    async def read(self):
        data = await self._queue.get()
        self._queue.task_done()
        return data
