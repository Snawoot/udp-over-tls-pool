import asyncio
import logging

class UDPListener:
    _loop = None
    _transport = None
    _expiration_task = None

    def __init__(self, address, port, session_factory, *, expire=120):
        self._address = address
        self._port = port
        self._session_factory = session_factory
        self._expire = expire
        self._logger = logging.getLogger(self.__class__.__name__)
        self._sessions = dict()
        self._expirations = dict()

    async def _watch_expirations(self):
        """ Stop idle sessions. This function could use some improvement,
        but it should work anyway. """
        while True:
            await asyncio.sleep(1)
            keys = []
            sessions = []
            for k, exp_time in self._expirations.iteritems():
                if exp_time < self._loop.time():
                    keys.append(k)
                    sessions.append(self._sessions[k])
            # Hide expired sessions and stop them
            for k in keys:
                del self._sessions[k]
                del self._expirations[k]
            keys = None
            await asyncio.gather(*(session.stop() for session in sessions))

    async def start(self):
        self._loop = asyncio.get_event_loop()
        self._expiration_task = asyncio.ensure_future(self._watch_expirations)
        self._transport, _ = await loop.create_datagram_endpoint(lambda: self,
            local_addr=(self._address, self._port))

    async def stop(self):
        self._transport.close()
        self._expiration_task.cancel()
        while not self._expiration_task.done():
            try:
                await self._expiration_task
            except asyncio.CancelledError:
                pass
        await asyncio.gather(*(session.stop() for session in self._sessions.values()))

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.stop()

    def connection_made(self, transport):
        pass

    def datagram_received(self, data, addr):
        self._expirations[addr] = self._loop.time() + self._expire
        if addr in self._sessions:
            session = self._sessions[addr]
        else:
            session = self._session_factory()
            self._sessions[addr] = session
