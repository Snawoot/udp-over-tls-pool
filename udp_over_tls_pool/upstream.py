import asyncio
import logging

from .constants import LEN_FORMAT, LEN_BYTES

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
        self._worker_task = asyncio.ensure_future(self._worker())
        self._logger.debug("Connection %s for session %s started",
                           id(self), self._sess_id.hex)

    async def stop(self):
        self._worker_task.cancel()
        while not self._worker_task.done():
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._logger.debug("Connection %s for session %s stopped",
                           id(self), self._sess_id.hex)

    async def _downstream(self, reader):
        while True:
            len_bytes = await reader.readexactly(LEN_BYTES)
            length = LEN_FORMAT.unpack(len_bytes)
            data = await reader.readexactly(length)
            self._recv_cb(data)

    async def _upstream(self, writer):
        while True:
            data = await self._queue.get()
            writer.write(LEN_FORMAT.pack(len(data)) + data)
            await writer.drain()
            self._queue.task_done()

    async def _do_backoff(self):
        await asyncio.sleep(self._backoff)

    async def _worker(self):
        while True:
            writer = None
            try:
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(self._host, self._port,
                                                ssl=self._ssl_ctx),
                        self._timeout)
                except asyncio.TimeoutError:
                    self._logger.warning("Connection %d for session %s: "
                                         "timeout",
                                         id(self), self._sess_id.hex)
                    await self._do_backoff()
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._logger.error("Error while connecting to upstream: %s",
                                       str(exc))
                    await self._do_backoff()
                    continue

                writer.write(self._sess_id.bytes)
                writer.transport.set_write_buffer_limits(0)
                rd_task = asyncio.ensure_future(self._downstream(reader))
                wr_task = asyncio.ensure_future(self._upstream(writer))
                try:
                    await asyncio.gather(rd_task, wr_task)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    for task in (rd_task, wr_task):
                        if not task.done():
                            task.cancel()
                        while not task.done():
                            try:
                                await task
                            except asyncio.CancelledError:
                                pass
                    self._logger.info("Connection %s for session %s has been "
                                      "stopped for a reason: %s",
                                      id(self), self._sess_id.hex, str(exc))
                    await self._do_backoff()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.exception("Connection %s for session %s: "
                                       "unhandled exception %s",
                                       id(self), self._sess_id.hex, str(exc))
                await self._do_backoff()
            finally:
                if writer is not None:
                    writer.close()
