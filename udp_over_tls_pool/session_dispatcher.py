import asyncio
import logging
import enum
from functools import partial

class ARCState(enum.Enum):
    CREATED = 1
    STARTED = 2
    STOPPED = 3

class UpstreamARC:
    _state = ARCState.CREATED
    _refcount = 0
    _endpoint = None
    _startup = None

    def __init__(self, upstream_factory, delete_cb):
        self._upstream_factory = upstream_factory
        self._delete_cb = delete_cb
        self._logger = logging.getLogger(self.__class__.__name__)

    async def __aenter__(self):
        if self._state is ARCState.CREATED:
            self._refcount += 1
            self._logger.debug("ARC 0x%x created, refcount = %d",
                               id(self), self._refcount)
            self._state = ARCState.STARTED
            loop = asyncio.get_event_loop()
            self._startup = loop.create_future()
            self._endpoint = self._upstream_factory()
            await self._endpoint.start()
            self._startup.set_result(True)
            self._logger.debug("ARC 0x%x started, refcount = %d",
                               id(self), self._refcount)
        elif self._state is ARCState.STARTED:
            self._refcount += 1
            if self._startup.done():
                self._logger.debug("ARC 0x%x increment w/o await, refcount = %d",
                                   id(self), self._refcount)
            else:
                await self._startup
                self._logger.debug("ARC 0x%x increment w/ await, refcount = %d",
                                   id(self), self._refcount)
        elif self._state is ARCState.STOPPED:
            raise RuntimeError("Attempted to borrow from disposed ARC")
        return self._endpoint

    async def __aexit__(self, exc_type, exc_value, traceback):
        self._refcount -= 1
        if self._refcount <= 0:
            self._state = ARCState.STOPPED
            self._delete_cb()
            await self._endpoint.stop()
            self._logger.debug("ARC 0x%x disposed", id(self))

class SessionDispatcher:
    def __init__(self, upstream_factory):
        self._upstream_factory = upstream_factory
        self._sessions = dict()
        self._logger = logging.getLogger(self.__class__.__name__)

    def _remove_session(self, session):
        self._sessions.pop(session, None)

    def dispatch(self, session):
        if session in self._sessions:
            self._logger.debug("Reusing ARC for session %s", session)
            return self._sessions[session]
        else:
            self._logger.debug("Dispatching new ARC for session %s", session)
            arc = UpstreamARC(self._upstream_factory,
                              partial(self._remove_session, session))
            self._sessions[session] = arc
            return arc
