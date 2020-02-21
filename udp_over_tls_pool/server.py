import sys
import argparse
import asyncio
import logging
import ssl
import signal
from functools import partial

from .asdnotify import AsyncSystemdNotifier
from . import dgram_upstream
from . import session_dispatcher
from . import stream_listener
from .constants import LogLevel
from . import utils


def parse_args():
    parser = argparse.ArgumentParser(
        description="UDP-over-TLS-pool. Server-side application.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("dst_address",
                        help="target hostname")
    parser.add_argument("dst_port",
                        type=utils.check_port,
                        help="target UDP port")
    parser.add_argument("-v", "--verbosity",
                        help="logging verbosity",
                        type=utils.check_loglevel,
                        choices=LogLevel,
                        default=LogLevel.info)
    parser.add_argument("-l", "--logfile",
                        help="log file location",
                        metavar="FILE")

    listen_group = parser.add_argument_group('listen options')
    listen_group.add_argument("-a", "--bind-address",
                              default="0.0.0.0",
                              help="TLS/TCP bind address")
    listen_group.add_argument("-p", "--bind-port",
                              default=8443,
                              type=utils.check_port,
                              help="TLS/TCP bind port")

    tls_group = parser.add_argument_group('TLS options')
    tls_group.add_argument("--no-tls",
                           action="store_false",
                           dest="tls",
                           help="do not use TLS")
    tls_group.add_argument("-c", "--cert",
                           help="use certificate for server TLS auth")
    tls_group.add_argument("-k", "--key",
                           help="key for TLS certificate")
    tls_group.add_argument("-C", "--cafile",
                           help="authenticate clients using following "
                           "CA certificate file")
    return parser.parse_args()


async def amain(args, loop):  # pragma: no cover
    logger = logging.getLogger('MAIN')

    if args.tls:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        if args.cafile:
            context.load_verify_locations(cafile=args.cafile)
            context.verify_mode = ssl.CERT_REQUIRED
        if args.cert is None or args.key is None:
            logger.fatal("Certificate or key is not specified but is TLS enabled")
            sys.exit(2)
        context.load_cert_chain(certfile=args.cert, keyfile=args.key)
    else:
        context = None

    upstream_factory = lambda: dgram_upstream.DgramUpstream(args.dst_address, args.dst_port)
    dispatcher = session_dispatcher.SessionDispatcher(upstream_factory)
    listener = stream_listener.StreamListener(args.bind_address, args.bind_port,
                                              context, dispatcher)
    async with listener:
        logger.info("%s server started", "TLS" if args.tls else "TCP")

        exit_event = asyncio.Event()
        async with utils.Heartbeat():
            sig_handler = partial(utils.exit_handler, exit_event)
            signal.signal(signal.SIGTERM, sig_handler)
            signal.signal(signal.SIGINT, sig_handler)
            async with AsyncSystemdNotifier() as notifier:
                await notifier.notify(b"READY=1")
                await exit_event.wait()

                logger.debug("Eventloop interrupted. Shutting down server...")
                await notifier.notify(b"STOPPING=1")
    logger.info("%s server stopped", "TLS" if args.tls else "TCP")


def main():  # pragma: no cover
    args = parse_args()
    with utils.AsyncLoggingHandler(args.logfile) as log_handler:
        logger = utils.setup_logger('MAIN', args.verbosity, log_handler)
        utils.setup_logger('DgramUpstream', args.verbosity, log_handler)
        utils.setup_logger('SessionDispatcher', args.verbosity, log_handler)
        utils.setup_logger('UpstreamARC', args.verbosity, log_handler)
        utils.setup_logger('StreamListener', args.verbosity, log_handler)

        logger.info("Starting eventloop...")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(amain(args, loop))
        loop.close()
        logger.info("Exiting...")
