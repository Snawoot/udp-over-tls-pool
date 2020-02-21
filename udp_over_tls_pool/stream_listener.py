import asyncio
import logging
import uuid
from functools import partial

from .constants import LEN_BYTES, LEN_FORMAT, UUID_BYTES

class StreamListener:
    _loop = None
    _server = None
    _stopping = False

    def __init__(self, host, port, ssl, dispatcher):
        self._host = host
        self._port = port
        self._ssl = ssl
        self._dispatcher = dispatcher
        self._children = set()
        self._logger = logging.getLogger(self.__class__.__name__)

    async def start(self):
        self._loop = asyncio.get_event_loop()
        def _spawn(reader, writer):
            if self._stopping:
                return
            def task_cb(task, fut):
                self._children.discard(task)
            task = self._loop.create_task(self.handler(reader, writer))
            self._children.add(task)
            task.add_done_callback(partial(task_cb, task))

        self._server = await asyncio.start_server(_spawn,
                                                  self._host,
                                                  self._port,
                                                  ssl=self._ssl)
        self._logger.info("Server ready.")

    async def stop(self):
        self._server.close()
        self._stopping = True
        await self._server.wait_closed()
        while self._children:
            children = list(self._children)
            self._children.clear()
            self._logger.debug("Cancelling %d client handlers...",
                               len(children))
            for task in children:
                task.cancel()
            await asyncio.wait(children)
            # workaround for TCP server keeps spawning handlers for a while
            # after wait_closed() completed
            await asyncio.sleep(.5)

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.stop()

    async def _upstream(self, reader, endpoint):
        while True:
            len_bytes = await reader.readexactly(LEN_BYTES)
            length = LEN_FORMAT.unpack(len_bytes)[0]
            data = await reader.readexactly(length)
            endpoint.write(data)

    async def _downstream(self, writer, endpoint):
        while True:
            data = await endpoint.read()
            writer.write(LEN_FORMAT.pack(len(data)) + data)
            await writer.drain()

    async def handler(self, reader, writer):
        peer_addr = writer.transport.get_extra_info('peername')
        self._logger.info("Client %s connected", str(peer_addr))
        try:
            # Get session ID
            try:
                sessid_bytes = await reader.readexactly(UUID_BYTES)
                sess_id = uuid.UUID(bytes=sessid_bytes)
            except (asyncio.IncompleteReadError, ConnectionResetError):
                self._logger.warning("Connection with %s was reset before "
                                     "session ID was read", peer_addr)
                return

            writer.transport.set_write_buffer_limits(0)

            # Obtain UDP endpoint and start operation
            async with self._dispatcher.dispatch(sess_id) as endpoint:
                rd_task = asyncio.ensure_future(self._upstream(reader, endpoint))
                wr_task = asyncio.ensure_future(self._downstream(writer, endpoint))
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
                                      id(self), sess_id.hex, str(exc))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._logger.exception("Got exception in connection handler: %s",
                                   str(exc))
        finally:
            writer.close()
            self._logger.info("Client %s disconnected", str(peer_addr))
