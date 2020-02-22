import asyncio
import logging
import socket

from .constants import LEN_FORMAT, LEN_BYTES

async def open_custom_connection(host, port, *, mark=None, **kwds):
    loop = asyncio.get_event_loop()
    addr_infos = await loop.getaddrinfo(host, port,
                                        type=socket.SOCK_STREAM,
                                        proto=socket.IPPROTO_TCP)
    my_exc = None
    for ai in addr_infos:
        try:
            fam, typ, proto, cname, addr = ai
            sock = socket.socket(fam, typ, proto)
            if mark is not None:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_MARK, mark)
            sock.setblocking(False)
            await loop.sock_connect(sock, addr)
            break
        except OSError as exc:
            my_exc = exc
    else:
        raise my_exc

    new_kwds = dict(kwds)
    new_kwds['sock'] = sock
    if kwds.get('ssl') is not None and kwds.get('server_hostname') is None:
        new_kwds['server_hostname'] = host
    return await asyncio.open_connection(**new_kwds)

class UpstreamConnection:
    def __init__(self, host, port, ssl_ctx, server_name, sess_id, recv_cb,
                 queue, *, timeout=4, backoff=5, mark=None):
        self._host = host
        self._port = port
        self._ssl_ctx = ssl_ctx
        self._server_name = server_name
        self._sess_id = sess_id
        self._recv_cb = recv_cb
        self._queue = queue
        self._timeout = timeout
        self._backoff = backoff
        self._mark = mark
        self._logger = logging.getLogger(self.__class__.__name__)
        self._worker_task = asyncio.ensure_future(self._worker())
        self._logger.debug("Connection 0x%x for session %s started",
                           id(self), self._sess_id.hex)

    async def stop(self):
        self._worker_task.cancel()
        while not self._worker_task.done():
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._logger.debug("Connection 0x%x for session %s stopped",
                           id(self), self._sess_id.hex)

    async def _downstream(self, reader):
        while True:
            len_bytes = await reader.readexactly(LEN_BYTES)
            length = LEN_FORMAT.unpack(len_bytes)[0]
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
                        open_custom_connection(self._host, self._port,
                                               ssl=self._ssl_ctx,
                                               server_hostname=self._server_name,
                                               mark=self._mark),
                        self._timeout)
                except asyncio.TimeoutError:
                    self._logger.warning("Connection 0x%x for session %s: "
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
                    self._logger.info("Connection 0x%x for session %s has been "
                                      "stopped for a reason: %s",
                                      id(self), self._sess_id.hex, str(exc))
                    await self._do_backoff()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.exception("Connection 0x%x for session %s: "
                                       "unhandled exception %s",
                                       id(self), self._sess_id.hex, str(exc))
                await self._do_backoff()
            finally:
                if writer is not None:
                    writer.close()
