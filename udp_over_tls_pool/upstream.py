import asyncio
import logging

class UpstreamConnection:
    def __init__(self, host, port, ssl_ctx, sess_id, recv_cb, queue, *,
                 timeout=4, backoff=5):
        self._host = host
        self._port = port
        self._ssl_ctx = ssl_ctx
        self._sess_id = sess_id
        self._recv_cb = recv_cb
        self._queue = queue
        self._timeout = timeout
        self._backoff = backoff
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.debug("Connection %s for session %s started",
                           id(self), self._sess_id.hex)

    async def stop(self):
        self._logger.debug("Connection %s for session %s stopped",
                           id(self), self._sess_id.hex)
