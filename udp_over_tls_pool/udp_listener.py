import asyncio
import logging
from functools import partial

from .constants import EXPIRE_GRACE

class UDPListener:
    _loop = None
    _transport = None
    _expiration_task = None
    _started = False
    _done = None
    _conn_event = None

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
        try:
            while True:
                if self._expirations:
                    closest_expire = min(self._expirations.values())
                    delay = closest_expire - self._loop.time() + 1
                    self._logger.debug("Sleeping until next possible expiration "
                                       "for %.3f seconds", delay)
                    await asyncio.sleep(delay)
                else:
                    self._logger.debug("No connections to expire. Waiting for "
                                       "connection event...")
                    await self._conn_event.wait()
                    self._conn_event.clear()
                    continue
                keys = []
                sessions = []
                curr_time = self._loop.time()
                for k, exp_time in self._expirations.items():
                    if exp_time < curr_time:
                        keys.append(k)
                        sessions.append(self._sessions[k])
                # Hide expired sessions and stop them
                for k in keys:
                    del self._sessions[k]
                    del self._expirations[k]
                self._conn_event.clear()
                await asyncio.gather(*(session.stop() for session in sessions))
                if keys:
                    self._logger.debug("Cleared endpoints %s due to inactivity",
                                       repr(keys))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._logger.exception("Got exception in expiration coroutine: %s",
                                   str(exc))

    async def start(self):
        self._loop = asyncio.get_event_loop()
        self._done = self._loop.create_future()
        self._conn_event = asyncio.Event()
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
        await self._done
        self._logger.info("Listener stopped")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.stop()

    def connection_made(self, transport):
        pass

    def connection_lost(self, transport):
        self._done.set_result(True)

    def _send_cb(self, addr, data):
        if self._started:
            self._update_expiration(addr)
            self._transport.sendto(data, addr)

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
                self._conn_event.set()
            session.enqueue(data)
