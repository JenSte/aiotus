from __future__ import annotations

import dataclasses
import io
import math
import os.path
import tempfile
from typing import Any, Generator, Mapping, Optional

import aiohttp
import pytest
import pytest_aiohttp
import pytest_asyncio
import yarl
from xprocess import ProcessStarter, XProcess  # type: ignore


@dataclasses.dataclass
class MockTusServer:
    # Number of times the respective handlers will fail.
    retries_create: int
    retries_options: int
    retries_head: int
    retries_upload: int

    # URLs to create and upload.
    create_endpoint: yarl.URL
    upload_endpoint: yarl.URL

    # The uploaded data will be accumulated here.
    data: Optional[bytearray]

    # Metadata included in the creation will be placed here.
    metadata: Optional[str]

    # Complete HTTP headers used in the last head/post request.
    head_headers: Optional[Mapping[str, str]]
    post_headers: Optional[Mapping[str, str]]

    # Drop some bytes while uploading, but don't return an error.
    drop_upload: bool

    # The aiohttp test server object.
    server: aiohttp.test_utils.TestServer


@pytest_asyncio.fixture
async def tus_server(aiohttp_server: pytest_aiohttp.AiohttpServer) -> MockTusServer:
    """Return a fake tus server that can consume a single file."""

    async def handler_create(request: aiohttp.web.Request) -> aiohttp.web.Response:
        server: MockTusServer = request.app["state"]["server"]

        server.retries_create -= 1
        if server.retries_create > 0:
            raise aiohttp.web.HTTPInternalServerError()

        if "Upload-Metadata" in request.headers:
            server.metadata = request.headers["Upload-Metadata"]

        server.post_headers = request.headers

        # "Create" the upload.
        server.data = bytearray()

        headers = {"Location": str(server.upload_endpoint)}
        raise aiohttp.web.HTTPCreated(headers=headers)

    async def handler_options(request: aiohttp.web.Request) -> aiohttp.web.Response:
        server: MockTusServer = request.app["state"]["server"]

        server.retries_options -= 1
        if server.retries_options > 0:
            raise aiohttp.web.HTTPInternalServerError()

        headers = {
            "Tus-Resumable": "1.0.0",
            "Tus-Version": "1.0.0",
            "Tus-Extension": "creation",
        }

        raise aiohttp.web.HTTPNoContent(headers=headers)

    async def handler_head(request: aiohttp.web.Request) -> aiohttp.web.Response:
        server: MockTusServer = request.app["state"]["server"]

        server.retries_head -= 1
        if server.retries_head > 0:
            raise aiohttp.web.HTTPInternalServerError()

        server.head_headers = request.headers

        if server.data is None:
            raise aiohttp.web.HTTPNotFound()

        headers = {"Upload-Offset": str(len(server.data))}
        if server.metadata is not None:
            headers["Upload-Metadata"] = server.metadata
        raise aiohttp.web.HTTPOk(headers=headers)

    async def handler_upload(request: aiohttp.web.Request) -> aiohttp.web.Response:
        server: MockTusServer = request.app["state"]["server"]

        body = await request.read()

        if server.data is None:
            raise aiohttp.web.HTTPUnprocessableEntity()

        if int(request.headers["Upload-Offset"]) != len(server.data):
            raise aiohttp.web.HTTPConflict()

        server.retries_upload -= 1
        if server.retries_upload > 0:
            # Pretend we did only receive half of the data before an error happend.
            server.data.extend(body[: len(body) // 2])
            raise aiohttp.web.HTTPInternalServerError()

        if server.drop_upload:
            # Simulate the situation where the server can only store a subset
            # of the data that was uploaded. (In contrast to the error that we simulate
            # above we do not return an HTTP error status code.)
            body = body[: math.ceil(len(body) / 2.0)]

        server.data.extend(body)
        headers = {"Tus-Resumable": "1.0.0", "Upload-Offset": str(len(server.data))}
        raise aiohttp.web.HTTPNoContent(headers=headers)

    upload_name = "1234abcdefgh"

    app = aiohttp.web.Application()
    app["state"] = {}
    app.router.add_route("POST", "/files", handler_create)
    app.router.add_route("OPTIONS", "/files", handler_options)
    app.router.add_route("HEAD", "/files/" + upload_name, handler_head)
    app.router.add_route("PATCH", "/files/" + upload_name, handler_upload)

    http_server = await aiohttp_server(app)
    create_endpoint = http_server.make_url("/files")
    upload_endpoint = create_endpoint / upload_name

    server = MockTusServer(
        retries_create=0,
        retries_options=0,
        retries_head=0,
        retries_upload=0,
        create_endpoint=create_endpoint,
        upload_endpoint=upload_endpoint,
        data=None,
        metadata=None,
        head_headers=None,
        post_headers=None,
        drop_upload=False,
        server=http_server,
    )

    app["state"]["server"] = server

    return server


@pytest.fixture
def memory_file() -> io.BytesIO:
    """Dummy data to use during tests."""
    return io.BytesIO(b"\x00\x01\x02\x03")


class EOFBytesIO:
    """A wrapper around 'io.BytesIO' that never returns data."""

    def __init__(self, b: io.BytesIO) -> None:
        self._b = b

    def seek(self, *args: Any, **kwargs: Any) -> int:
        return self._b.seek(*args, **kwargs)

    def read(self, *args: Any, **kwargs: Any) -> bytes:
        return b""


@pytest.fixture
def eof_memory_file(memory_file: io.BytesIO) -> io.BytesIO:
    # The two functions implemented by 'BinaryIO' are the only
    # ones aiotus uses, so the type error can be ignored.
    return EOFBytesIO(memory_file)  # type: ignore[return-value]


@dataclasses.dataclass
class TusServer:
    # The URL where the server is listening on.
    url: yarl.URL

    # The path of the certificate file of the server, if TLS is used.
    certificate: Optional[str] = None


@pytest.fixture(scope="module")
def tusd(pytestconfig: pytest.Config, xprocess: XProcess) -> Generator[TusServer]:
    """Start the tusd (tus.io reference implementation) and yield the upload URL.

    Assumes that the tusd executable is located in the pytest rootdir.
    """

    host = "0.0.0.0"
    port = "8080"
    basepath = "/files/"

    executable = pytestconfig.rootpath / "tusd"

    class Starter(ProcessStarter):  # type: ignore[misc]
        pattern = "You can now upload files to:"
        args = [str(executable), "-host", host, "-port", port, "-base-path", basepath]
        terminate_on_interrupt = True

    server_name = "tusd-server"

    xprocess.ensure(server_name, Starter)
    server = TusServer(yarl.URL(f"http://{host}:{port}{basepath}"))
    yield server
    xprocess.getinfo(server_name).terminate()


# Template for the nginx configuration file. Stripped-down from
# https://github.com/tus/tusd/blob/master/examples/nginx.conf
_nginx_conf = """
    pid nginx.pid;
    daemon off;
    error_log /dev/null;

    events {{
    }}

    http {{
        client_body_temp_path ./client_body;
        proxy_temp_path ./proxy;
        fastcgi_temp_path ./fastcgi;
        uwsgi_temp_path ./uwsgi;
        scgi_temp_path ./scgi;

        access_log off;

        server {{
            listen {port} ssl;
            server_name _;
            ssl_certificate {crt};
            ssl_certificate_key {key};

            location / {{
                # Forward incoming requests to local tusd instance
                proxy_pass {tusd_url};

                # Disable request and response buffering
                proxy_request_buffering  off;
                proxy_buffering off;
                proxy_http_version 1.1;

                # Add X-Forwarded-* headers
                proxy_set_header X-Forwarded-Host $hostname;
                proxy_set_header X-Forwarded-Proto $scheme;

                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection "upgrade";
                client_max_body_size 0;
            }}
        }}
    }}
"""


@pytest.fixture(scope="module")
def nginx_proxy(xprocess: XProcess, tusd: TusServer) -> Generator[TusServer]:
    """Start an nginx proxy in front of tusd that does TLS termination."""

    test_dir = os.path.dirname(os.path.abspath(__file__))
    certificate = os.path.join(test_dir, "selfsigned.crt")
    fmt = {
        "crt": certificate,
        "key": os.path.join(test_dir, "nginx.key"),
        "port": 8443,
        "tusd_url": str(tusd.url),
    }
    conf = _nginx_conf.format(**fmt)

    with tempfile.TemporaryDirectory() as d:
        conf_file = os.path.join(d, "nginx.conf")
        with open(conf_file, "w") as f:
            f.write(conf)

        class Starter(ProcessStarter):  # type: ignore[misc]
            pattern = "could not open error log file"
            args = ["nginx", "-p", d, "-c", "nginx.conf"]
            terminate_on_interrupt = True

        server_name = "nginx-server"

        xprocess.ensure(server_name, Starter)
        server = TusServer(yarl.URL(f"https://localhost:{fmt['port']}"))
        server.certificate = certificate
        yield server
        xprocess.getinfo(server_name).terminate()
