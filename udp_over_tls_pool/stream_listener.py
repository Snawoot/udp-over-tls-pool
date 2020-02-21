import asyncio
import logging
import uuid

from .constants import LEN_BYTES, LEN_FORMAT, UUID_BYTES

class StreamListener:
    def __init__(self, host, port, dispatcher):
        self._host = host
        self._port = port
        self._dispatcher = dispatcher
        self._children = set()
        self._server = None
        self._logger = logging.getLogger(self.__class__.__name__)

    async def start(self):
        def _spawn(reader, writer):
            def task_cb(task, fut):
                self._children.discard(task)
            task = self._loop.create_task(self.handler(reader, writer))
            self._children.add(task)
            task.add_done_callback(partial(task_cb, task))

        self._server = await asyncio.start_server(_spawn,
                                                  self._listen_address,
                                                  self._listen_port)
        self._logger.info("Server ready.")

    async def stop(self):
        self._server.close()
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

    async def handler(self, reader, writer):
        peer_addr = writer.transport.get_extra_info('peername')
        self._logger.info("Client %s connected", str(peer_addr))
        try:
            try:
                sessid_bytes = await reader.readexactly(UUID_BYTES)
                sess_id = uuid.UUID(bytes=sessid_bytes)
            except asyncio.IncompleteReadError, ConnectionResetError:
                self._logger.warning("Connection with %s was reset before "
                                     "session ID was read", peer_addr)
                return
            async with self._dispatcher.dispatch(sess_id) as endpoint:
                pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._logger.exception("Got exception in connection handler: %s",
                                   str(exc))
        finally:
            writer.close()
