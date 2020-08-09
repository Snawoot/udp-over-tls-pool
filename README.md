udp-over-tls-pool
=================

[![udp-over-tls-pool](https://snapcraft.io//udp-over-tls-pool/badge.svg)](https://snapcraft.io/udp-over-tls-pool)

Network wrapper which transports UDP packets over multiple TLS sessions (or plain TCP connections).

Client-side application listens UDP port and for each sending endpoint it establishes multiple connections to server-side application. Server side application maintains UDP endpoint socket for each group of incoming connections and forwards data to destination UDP socket.

`udp-over-tls-pool` can be used as a transport for Wireguard or other UDP VPN protocols in cases where plain UDP transit is impossible or undesirable.

---

:heart: :heart: :heart:

You can say thanks to the author by donations to these wallets:

- ETH: `0xB71250010e8beC90C5f9ddF408251eBA9dD7320e`
- BTC:
  - Legacy: `1N89PRvG1CSsUk9sxKwBwudN6TjTPQ1N8a`
  - Segwit: `bc1qc0hcyxc000qf0ketv4r44ld7dlgmmu73rtlntw`

---

## Features

* Based on proven TLS security
* Uses multiple connections for greater performance
* Cross-plaform: runs on Linux, macOS, Windows and other Unix-like systems.

## Requirements

* Python 3.5.3+

## Installation

#### From PyPI

```
pip3 install udp-over-tls-pool
```

#### From Snap Store

[![Get it from the Snap Store](https://snapcraft.io/static/images/badges/en/snap-store-black.svg)](https://snapcraft.io/udp-over-tls-pool)

```
sudo snap install udp-over-tls-pool
```

Note that binaries installed by snap are named `udp-over-tls-pool.server` and `udp-over-tls-pool.client`.

## Usage

Server example:

```
uotp-server -c /etc/letsencrypt/live/example.com/fullchain.pem \
    -k /etc/letsencrypt/live/example.com/privkey.pem \
    127.0.0.1 26611
```

where 26611 is a target UDP service port. By default server accepts connections on port 8443.

Client example:

```
uotp-client -a 0.0.0.0 example.com 8443
```

where `0.0.0.0` is a listen address (default is localhost only) and `example.com 8443` is uotp-server host address and port. By default client listens UDP port 8911.

See Synopsis for more options.

## Using as a transport for VPN

This application can be used as a transport for UDP-based VPN like Wireguard or OpenVPN.

In case when udp-over-tls-pool server address is covered by routing prefixes tunneled through VPN (for example, if VPN replaces default gateway), udp-over-tls-pool traffic must be excluded. Otherwise connections from uotp-client to uotp-server will be looped back to tunnel. There are at least two ways to resolve that loop.

### Excluding uotp-client traffic with a static route

Classic solution is to define specific route to host with udp-over-tls-pool server. Here is an example Wireguard configuration for Linux:

```
[Interface]
Address = 172.21.123.2/32
PrivateKey = XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
PreUp = ip route add 198.51.100.1/32 $(ip route show default | cut -f2- -d\ )
PostDown = ip route del 198.51.100.1/32

[Peer]
PublicKey = YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY
Endpoint = 127.0.0.1:8911
AllowedIPs = 0.0.0.0/0
```

where `198.51.100.1` is an IP address of host with uotp-server.

Such solution should work on all platforms and operating systems, though it leaves all other traffic to uotp-server host unprotected.

### Excluding uotp-client traffic with rule-based routing

Some VPN tunnels use rule-based routing on Linux to exclude own packets from tunnel itself. For example, Wireguard started with `wg-quick` command uses netfilter mark to distinguish tunnel carrier packets. uotp-client is capable to mark own TCP/TLS packets with nfmark as well. To enable this feature you may run uotp-client like this:

```
uotp-client --resolve-once --mark 0xca6c example.com 8443
```

where `0xca6c` is default fwmark for Wireguard set by `wg-quick`. You may check this value with `wg show INTERFACE fwmark`. Once this is enabled no additional for Wireguard configuration is required.

Note that to use netfilter marks uotp-client has to be run as superuser or process has to be started with `CAP_NET_ADMIN` capability. You may set this capability for a process running as restricted user with systemd service file like one below:

```
# /etc/systemd/system/uotp-client.service
[Unit]
Description=UDP over TLS pool client
After=syslog.target network.target

[Service]
Type=notify
User=uotp-client
AmbientCapabilities=CAP_NET_ADMIN
ExecStart=/usr/local/bin/uotp-client --resolve-once --mark 0xca6c example.com 8443
Restart=always
KillMode=process

[Install]
WantedBy=multi-user.target
```

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
                   [-a BIND_ADDRESS] [-p BIND_PORT] [-e EXPIRE] [-n POOL_SIZE]
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
  -e EXPIRE, --expire EXPIRE
                        UDP session idle timeout in seconds (default: 120.0)

pool options:
  -n POOL_SIZE, --pool-size POOL_SIZE
                        connection pool size (default: 8)
  -B BACKOFF, --backoff BACKOFF
                        delay after connection attempt failure in seconds
                        (default: 5.0)
  -w TIMEOUT, --timeout TIMEOUT
                        server connect timeout in seconds (default: 4.0)

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
