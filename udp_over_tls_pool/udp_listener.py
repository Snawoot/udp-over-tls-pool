import asyncio
import logging
from functools import partial

class UDPListener:
    _loop = None
    _transport = None
    _expiration_task = None
    _started = False

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
            await asyncio.gather(*(session.stop() for session in sessions))
            self._logger.debug("Cleared endpoints %s due to inactivity",
                               repr(keys))

    async def start(self):
        self._loop = asyncio.get_event_loop()
        self._expiration_task = asyncio.ensure_future(self._watch_expirations())
        self._transport, _ = await self._loop.create_datagram_endpoint(
            lambda: self, local_addr=(self._address, self._port))
        self._started = True
        self._logger.info("Listener started")

    async def stop(self):
        self._started = False
        self._transport.close()
        self._expiration_task.cancel()
        while not self._expiration_task.done():
            try:
                await self._expiration_task
            except asyncio.CancelledError:
                pass
        await asyncio.gather(*(session.stop() for session in self._sessions.values()))
        self._logger.info("Listener stopped")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.stop()

    def connection_made(self, transport):
        pass

    def connection_lost(self, transport):
        pass

    def _send_cb(self, addr, data):
        if self._started:
            self._update_expiration(addr)
            self._transport.sendto(addr, data)
            self._logger.debug("Sent %s to %s", repr(data), repr(addr))

    def _update_expiration(self, addr):
        self._expirations[addr] = self._loop.time() + self._expire

    def datagram_received(self, data, addr):
        if self._started:
            self._update_expiration(addr)
            if addr in self._sessions:
                session = self._sessions[addr]
            else:
                self._logger.info("New endpoint: %s", addr)
                session = self._session_factory(partial(self._send_cb, addr))
                self._sessions[addr] = session
            session.enqueue(data)
