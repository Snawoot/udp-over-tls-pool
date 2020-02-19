import asyncio
import argparse
import logging
import logging.handlers
import ssl
import os
import queue
import socket
import ctypes
import time

from . import constants


class OverflowingQueue(queue.Queue):
    def put(self, item, block=True, timeout=None):
        try:
            return queue.Queue.put(self, item, block, timeout)
        except queue.Full:
            pass

    def put_nowait(self, item):
        return self.put(item, False)


class AsyncLoggingHandler:
    def __init__(self, logfile=None, maxsize=1024):
        _queue = OverflowingQueue(maxsize)
        if logfile is None:
            _handler = logging.StreamHandler()
        else:
            _handler = logging.FileHandler(logfile)
        self._listener = logging.handlers.QueueListener(_queue, _handler)
        self._async_handler = logging.handlers.QueueHandler(_queue)

        _handler.setFormatter(logging.Formatter('%(asctime)s '
                                                '%(levelname)-8s '
                                                '%(name)s: %(message)s',
                                                '%Y-%m-%d %H:%M:%S'))

    def __enter__(self):
        self._listener.start()
        return self._async_handler

    def __exit__(self, exc_type, exc_value, traceback):
        self._listener.stop()


def setup_logger(name, verbosity, handler):
    logger = logging.getLogger(name)
    logger.setLevel(verbosity)
    logger.addHandler(handler)
    return logger


def check_port(value):
    def fail():
        raise argparse.ArgumentTypeError(
            "%s is not a valid port number" % value)
    try:
        ivalue = int(value)
    except ValueError:
        fail()
    if not 0 < ivalue < 65536:
        fail()
    return ivalue


def check_positive_float(value):
    def fail():
        raise argparse.ArgumentTypeError(
            "%s is not a valid value" % value)
    try:
        fvalue = float(value)
    except ValueError:
        fail()
    if fvalue <= 0:
        fail()
    return fvalue


def check_positive_int(value):
    def fail():
        raise argparse.ArgumentTypeError(
            "%s is not a valid value" % value)
    try:
        fvalue = int(value)
    except ValueError:
        fail()
    if fvalue <= 0:
        fail()
    return fvalue


def check_loglevel(arg):
    try:
        return constants.LogLevel[arg]
    except (IndexError, KeyError):
        raise argparse.ArgumentTypeError("%s is not valid loglevel" % (repr(arg),))


def check_ssl_hostname(arg):
    if not arg:
        raise argparse.ArgumentTypeError("%s is not valid server name" % (repr(arg),))
    return arg


def exit_handler(exit_event, signum, frame):  # pragma: no cover pylint: disable=unused-argument
    logger = logging.getLogger('MAIN')
    if exit_event.is_set():
        logger.warning("Got second exit signal! Terminating hard.")
        os._exit(1)  # pylint: disable=protected-access
    else:
        logger.warning("Got first exit signal! Terminating gracefully.")
        exit_event.set()


class Heartbeat:
    def __init__(self, interval=.5):
        self._interval = interval
        self._beat = None

    async def heartbeat(self):
        while True:
            await asyncio.sleep(self._interval)

    async def heartbeat(self):
        """ Hacky coroutine which keeps event loop spinning with some interval
        even if no events are coming. This is required to handle Futures and
        Events state change when no IO events are occuring."""
        while True:
            await asyncio.sleep(.5)

    async def __aenter__(self):
        return await self.start()

    async def start(self):
        if self._beat is None:
            self._beat = asyncio.ensure_future(self.heartbeat())
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return await self.stop()

    async def stop(self):
        self._beat.cancel()
        while not self._beat.done():
            try:
                print("Cancelling heartbeat...")
                await self._beat
            except asyncio.CancelledError:
                pass


async def wall_clock_sleep(duration, precision=.2):
    async def _wall_clock_sleep():
        end_time = time.time() + duration
        while time.time() < end_time:
            await asyncio.sleep(precision)

    try:
        await asyncio.wait_for(_wall_clock_sleep(), duration)
    except asyncio.TimeoutError:
        pass
