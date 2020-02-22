import enum
import logging
import struct


class LogLevel(enum.IntEnum):
    debug = logging.DEBUG
    info = logging.INFO
    warn = logging.WARN
    error = logging.ERROR
    fatal = logging.FATAL
    crit = logging.CRITICAL

    def __str__(self):
        return self.name


BUFSIZE = 16 * 1024
LEN_FORMAT = struct.Struct('!H')
LEN_BYTES = LEN_FORMAT.size
UUID_BYTES = 16
MAX_DGRAM_QLEN = 128
EXPIRE_GRACE = 1.
