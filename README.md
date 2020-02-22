udp-over-tls-pool
=================

Network wrapper which transports UDP packets over multiple TLS sessions (or plain TCP connections).

Client-side application listens UDP port and for each sending endpoint it establishes multiple connections to server-side application. Server side application maintains UDP endpoint socket for each group of incoming connections and forwards data to destination UDP socket.

`udp-over-tls-pool` can be used as a transport for Wireguard or other UDP VPN protocols in cases where plain UDP transit is impossible or undesirable.

## Features

* Based on proven TLS security
* Uses multiple connections for greater performance
* Cross-plaform: runs on Linux, macOS, Windows and other Unix-like systems.

## Requirements

* Python 3.5.3+

## Installation

```
pip3 install udp-over-tls-pool
```

## Usage

Server example:

```
uotp-server -c /etc/letsencrypt/live/example.com/fullchain.pem \
    -k /etc/letsencrypt/live/example.com/privkey.pem \
    127.0.0.1 26611
```

where 26611 is a Wireguard UDP port. By default server accepts connections on port 8443.

Client example:

```
uotp-client -a 0.0.0.0 example.com 8443
```

where `0.0.0.0` is a listen address (default is localhost only) and `example.com 8443` is uotp-server host address and port. By default client listens UDP port 8911.

See Synopsis for more options.

## Synopsis

Server:

```
$ uotp-server --help
usage: uotp-server [-h] [-v {debug,info,warn,error,fatal}] [-l FILE]
                   [-a BIND_ADDRESS] [-p BIND_PORT] [--no-tls] [-c CERT]
                   [-k KEY] [-C CAFILE]
                   dst_address dst_port

UDP-over-TLS-pool. Server-side application.

positional arguments:
  dst_address           target hostname
  dst_port              target UDP port

optional arguments:
  -h, --help            show this help message and exit
  -v {debug,info,warn,error,fatal}, --verbosity {debug,info,warn,error,fatal}
                        logging verbosity (default: info)
  -l FILE, --logfile FILE
                        log file location (default: None)

listen options:
  -a BIND_ADDRESS, --bind-address BIND_ADDRESS
                        TLS/TCP bind address (default: 0.0.0.0)
  -p BIND_PORT, --bind-port BIND_PORT
                        TLS/TCP bind port (default: 8443)

TLS options:
  --no-tls              do not use TLS (default: True)
  -c CERT, --cert CERT  use certificate for server TLS auth (default: None)
  -k KEY, --key KEY     key for TLS certificate (default: None)
  -C CAFILE, --cafile CAFILE
                        authenticate clients using following CA certificate
                        file (default: None)
```

Client:

```
$ uotp-client --help
usage: uotp-client [-h] [-v {debug,info,warn,error,fatal}] [-l FILE]
                   [-a BIND_ADDRESS] [-p BIND_PORT] [-n POOL_SIZE]
                   [-B BACKOFF] [-w TIMEOUT] [--no-tls] [-c CERT] [-k KEY]
                   [-C CAFILE]
                   [--no-hostname-check | --tls-servername TLS_SERVERNAME]
                   dst_address dst_port

UDP-over-TLS-pool. Client-side application.

positional arguments:
  dst_address           target hostname
  dst_port              target port

optional arguments:
  -h, --help            show this help message and exit
  -v {debug,info,warn,error,fatal}, --verbosity {debug,info,warn,error,fatal}
                        logging verbosity (default: info)
  -l FILE, --logfile FILE
                        log file location (default: None)

listen options:
  -a BIND_ADDRESS, --bind-address BIND_ADDRESS
                        UDP bind address (default: 127.0.0.1)
  -p BIND_PORT, --bind-port BIND_PORT
                        UDP bind port (default: 8911)

pool options:
  -n POOL_SIZE, --pool-size POOL_SIZE
                        connection pool size (default: 8)
  -B BACKOFF, --backoff BACKOFF
                        delay after connection attempt failure in seconds
                        (default: 5)
  -w TIMEOUT, --timeout TIMEOUT
                        server connect timeout (default: 4)

TLS options:
  --no-tls              do not use TLS (default: True)
  -c CERT, --cert CERT  use certificate for client TLS auth (default: None)
  -k KEY, --key KEY     key for TLS certificate (default: None)
  -C CAFILE, --cafile CAFILE
                        override default CA certs by set specified in file
                        (default: None)
  --no-hostname-check   do not check hostname in cert subject. This option is
                        useful for private PKI and available only together
                        with "--cafile" (default: False)
  --tls-servername TLS_SERVERNAME
                        specifies hostname to expect in server TLS certificate
                        (default: None)
```
