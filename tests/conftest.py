import base64
import dataclasses
import io

import aiohttp
import pytest  # type: ignore
import yarl
from xprocess import ProcessStarter  # type: ignore


@pytest.fixture
async def tus_server(aiohttp_server):
    """Return a fake tus server that can consume a single file."""

    state = {
        # Number of times the respective handlers will fail.
        "retries_create": 0,
        "retries_offset": 0,
        "retries_upload": 0,
        # URLs to create and upload. (Filled out later.)
        "create_endpoint": None,
        "upload_endpoint": None,
        # The uploaded data will be accumulated here.
        "data": None,
        # Metadata included in the creation will be placed here.
        "metadata": {},
        # HTTP headers of the creation.
        "headers": None,
    }

    async def handler_create(request):
        state["retries_create"] -= 1
        if state["retries_create"] > 0:
            raise aiohttp.web.HTTPInternalServerError()

        if "Upload-Metadata" in request.headers:
            pairs = request.headers["Upload-Metadata"].split(", ")
            pairs = [p.split(" ", 1) for p in pairs]
            for k, v in pairs:
                state["metadata"][k] = base64.b64decode(v, validate=True).decode()

        state["headers"] = request.headers

        # "Create" the upload.
        state["data"] = bytearray()

        headers = {"Location": str(state["upload_endpoint"])}
        raise aiohttp.web.HTTPCreated(headers=headers)

    async def handler_offset(request):
        state["retries_offset"] -= 1
        if state["retries_offset"] > 0:
            raise aiohttp.web.HTTPInternalServerError()

        if state["data"] is None:
            raise aiohttp.web.HTTPNotFound()

        headers = {"Upload-Offset": str(len(state["data"]))}
        raise aiohttp.web.HTTPOk(headers=headers)

    async def handler_upload(request):
        body = await request.read()

        state["retries_upload"] -= 1
        if state["retries_upload"] > 0:
            # Pretend we did only receive half of the data before an error happend.
            state["data"].extend(body[: len(body) // 2])
            raise aiohttp.web.HTTPInternalServerError()

        state["data"].extend(body)
        raise aiohttp.web.HTTPNoContent()

    upload_name = "1234abcdefgh"

    app = aiohttp.web.Application()
    app.router.add_route("POST", "/files", handler_create)
    app.router.add_route("HEAD", "/files/" + upload_name, handler_offset)
    app.router.add_route("PATCH", "/files/" + upload_name, handler_upload)

    state["server"] = await aiohttp_server(app)
    state["create_endpoint"] = state["server"].make_url("/files")
    state["upload_endpoint"] = state["create_endpoint"] / upload_name

    return state


@pytest.fixture
def memory_file():
    """Dummy data to use during tests."""
    return io.BytesIO(b"\x00\x01\x02\x03")


@dataclasses.dataclass
class TusServer:

    # The URL where the server is listening on.
    url: yarl.URL


@pytest.fixture(scope="module")
def tusd(pytestconfig, xprocess):
    """Start the tusd (tus.io reference implementation) and yield the upload URL.

    Assumes that the tusd executable is located in the pytest rootdir.
    """

    host = "0.0.0.0"
    port = "8080"
    basepath = "/files/"

    executable = pytestconfig.rootdir.join("/tusd")

    class Starter(ProcessStarter):
        pattern = "You can now upload files to:"
        args = [executable, "-host", host, "-port", port, "-base-path", basepath]

    server_name = "tusd-server"

    xprocess.ensure(server_name, Starter)
    server = TusServer(yarl.URL(f"http://{host}:{port}{basepath}"))
    yield server
    xprocess.getinfo(server_name).terminate()
