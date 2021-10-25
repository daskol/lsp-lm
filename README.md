# LSP: Language Model

*Language Model as a Language Server*

## Overview

### Features

- [x] Completion (context-aware continuation sudgestions).
- [ ] Diagnostics (spelling, grammar, etc).
- [ ] Go to Definition (aka thesaurus).

## Usage

At the moment there is only one implementation in Python which are aimed in
debugging interfaces and model evaluation. So, in order to run dev
implementation one can do the following in shell.
```shell
lsp-lm serve  # stdio:
```
With the command above one starts a language server to communicate over standard
I/O streams.

### IPC

In order to use standard inter-procedural communication channels, one can start
a language server to listen Unix domain socket (UDS) as follows.
```shell
lsp-lm serve unix://path/to/unix/domain/socket
```

### TCP

In case of modern multi-host environment, one can want to listen public TCP/IP
interface for remote access to a language server. So, serving TCP/IP (both v4
and v6) could be achieved with the command below.
```shell
lsp-lm serve tcp://0.0.0.0:5272
```
In order to serve IPv4 or IPv6 interfaces one should use URI schemata `tcp4://`
and `tcp6://` correspondently. Default port is `5272`.

Also, SSL/TLS could be used in order to protect connection in public or
unprotected networks with specifying certificate, private key, and (optional) password
files.
```shell
lsp-lm serve \
    --tls-cert cert.pem --tls-key key.pem --tls-pass password.txt \
    tcp://0.0.0.0:5272
```
Certificate and private key could be bundled in the same container. In this
instance one can omit `--tls-key` option. Password option is mandatory only if
private key is encrypted.

Surely, self-signed certificates are allowed. As a mild reminder, both
certificate and (encrypted) private key could be generated with OpenSSL as
follows.
```shell
cat password.txt
# strong-password-in-plain-text
openssl req -new -x509 -days 365 -out cert.pem -keyout key.pem -passout file:password.txt
openssl rsa -in key.pem -passin file:password.txt -check -noout
# RSA key ok
```

## Development with Docker

In order to develop on different platforms we uses custom docker image for
non-priviledge user based on Nvidia CUDA image. Image is parametrized by user
name and user ID in a host system. The latter is crucial thing in binding host
volumes.

```bash
docker build -t lsp-lm --build-arg UID=$(id -u) .
docker run --rm -ti -e TERM=$TERM -v $(pwd):/workspace lsp-lm
```

## Tasks Queue

1. Find suitable corpus in Russian (English).
    1. Download Wikipedia dumps.
    2. Read Wikipedia dumps according to XML schema.
    3. Write parsed Wikipedia dumps to Parquet files.
2. Develop preprocessing pipeline.
3. Use TensorFlow to describe and fit a model.
4. Freeze models weights and export.
5. Write service which implements LSP.
6. Load model graph and weights in LSP service.

## Assembly

There are multiple required dependencies.

1. Multi-threading support (e.g. POSIX Threads).
2. XML parsing library [Expat][2].
3. Data compression library [bzip2][3].
4. [Apache Arrow][1] library with support of compression codecs and Parquet.

We use CMake as a main building system. So, assembly is relatively simple.
```shell
cmake -B build/release
cmake --build build/release
```

[1]: https://github.com/apache/arrow
[2]: https://github.com/libexpat/libexpat
[3]: https://gitlab.com/federicomenaquintero/bzip2
