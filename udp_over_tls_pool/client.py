import sys
import argparse
import asyncio
import logging
import ssl
import signal
from functools import partial

from .asdnotify import AsyncSystemdNotifier
from . import upstream
from . import client_session
from . import udp_listener
from .constants import LogLevel
from . import utils


def parse_args():
    parser = argparse.ArgumentParser(
        description="UDP-over-TLS-pool. Client-side application.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument("dst_address",
                        help="target hostname")
    parser.add_argument("dst_port",
                        type=utils.check_port,
                        help="target port")
    parser.add_argument("-v", "--verbosity",
                        help="logging verbosity",
                        type=utils.check_loglevel,
                        choices=LogLevel,
                        default=LogLevel.info)
    parser.add_argument("-l", "--logfile",
                        help="log file location",
                        metavar="FILE")
    parser.add_argument("-R", "--resolve-once",
                        help="resolve destination address at startup "
                        "(useful for VPN transport when DNS becomes "
                        "unavailable directly)",
                        action="store_true")

    listen_group = parser.add_argument_group('listen options')
    listen_group.add_argument("-a", "--bind-address",
                              default="127.0.0.1",
                              help="UDP bind address")
    listen_group.add_argument("-p", "--bind-port",
                              default=8911,
                              type=utils.check_port,
                              help="UDP bind port")
    listen_group.add_argument("-e", "--expire",
                              default=120.,
                              type=utils.check_positive_float,
                              help="UDP session idle timeout in seconds")

    pool_group = parser.add_argument_group('pool options')
    pool_group.add_argument("-n", "--pool-size",
                            default=8,
                            type=utils.check_positive_int,
                            help="connection pool size")
    pool_group.add_argument("-B", "--backoff",
                            default=5.,
                            type=utils.check_positive_float,
                            help="delay after connection attempt failure in seconds")
    pool_group.add_argument("-w", "--timeout",
                            default=4.,
                            type=utils.check_positive_float,
                            help="server connect timeout in seconds")
    pool_group.add_argument("-m", "--mark",
                            type=utils.check_fwmark,
                            help="(Linux only) set nfmark for outbound TCP "
                            "connections")

    tls_group = parser.add_argument_group('TLS options')
    tls_group.add_argument("--no-tls",
                           action="store_false",
                           dest="tls",
                           help="do not use TLS")
    tls_group.add_argument("-c", "--cert",
                           help="use certificate for client TLS auth")
    tls_group.add_argument("-k", "--key",
                           help="key for TLS certificate")
    tls_group.add_argument("-C", "--cafile",
                           help="override default CA certs "
                           "by set specified in file")
    ssl_name_group=tls_group.add_mutually_exclusive_group()
    ssl_name_group.add_argument("--no-hostname-check",
                                action="store_true",
                                help="do not check hostname in cert subject. "
                                "This option is useful for private PKI and "
                                "available only together with \"--cafile\"")
    ssl_name_group.add_argument("--tls-servername",
                                type=utils.check_ssl_hostname,
                                help="specifies hostname to expect in server "
                                "TLS certificate")
    return parser.parse_args()


async def amain(args, loop):  # pragma: no cover
    logger = logging.getLogger('MAIN')

    ssl_hostname = None
    if args.tls:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        if args.cafile:
            context.load_verify_locations(cafile=args.cafile)
        if args.no_hostname_check:
            if not args.cafile:
                logger.fatal("CAfile option is required when hostname check "
                             "is disabled. Terminating program.")
                sys.exit(2)
            ssl_hostname = ''
        elif args.tls_servername:
            ssl_hostname = args.tls_servername
        else:
            ssl_hostname = args.dst_address
        if args.cert:
            context.load_cert_chain(certfile=args.cert, keyfile=args.key)
    else:
        context = None

    dst_host = (utils.resolve_tcp_endpoint(args.dst_address, args.dst_port)
                if args.resolve_once else args.dst_address)
    conn_factory = lambda sess_id, recv_cb, queue: upstream.UpstreamConnection(dst_host,
        args.dst_port, context, ssl_hostname, sess_id, recv_cb, queue,
        timeout=args.timeout, backoff=args.backoff, mark=args.mark)
    session_factory = lambda recv_cb: client_session.ClientSession(conn_factory,
                                                                   recv_cb,
                                                                   pool_size=args.pool_size)
    udp_server = udp_listener.UDPListener(args.bind_address,
                                          args.bind_port,
                                          session_factory,
                                          expire=args.expire)
    async with udp_server:
        logger.info("UDP server started.")

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
    logger.info("UDP server stopped.")


def main():  # pragma: no cover
    args = parse_args()
    with utils.AsyncLoggingHandler(args.logfile) as log_handler:
        logger = utils.setup_logger('MAIN', args.verbosity, log_handler)
        utils.setup_logger('UpstreamConnection', args.verbosity, log_handler)
        utils.setup_logger('ClientSession', args.verbosity, log_handler)
        utils.setup_logger('UDPListener', args.verbosity, log_handler)

        logger.info("Starting eventloop...")
        loop = asyncio.get_event_loop()
        loop.run_until_complete(amain(args, loop))
        loop.close()
        logger.info("Exiting...")
