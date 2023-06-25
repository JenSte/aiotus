from __future__ import annotations

import argparse
import asyncio
import logging
import mimetypes
import os.path
import sys

from . import retry


def _upload(args: argparse.Namespace) -> int:
    """Implementation of the "upload" command.

    :return: Exit status for the program.
    """

    metadata = {"filename": os.path.basename(args.file).encode()}

    if mime_type := mimetypes.guess_type(args.file)[0]:
        metadata["mime_type"] = mime_type.encode()

    for meta in args.metadata:
        kv = meta.split("=", maxsplit=1)
        metadata[kv[0]] = kv[1].encode() if (len(kv) == 2) else None

    try:
        with open(args.file, "rb") as file:
            if location := asyncio.run(retry.upload(args.endpoint, file, metadata)):
                print(str(location))
                return 0
    except KeyboardInterrupt:  # pragma: no cover
        pass
    except Exception as e:
        logging.error(f"Unable to upload file: {e}")

    return 1


def _metadata(args: argparse.Namespace) -> int:
    """Implementation of the "metadata" command.

    :return: Exit status for the program.
    """

    try:
        metadata = asyncio.run(retry.metadata(args.location))
        assert isinstance(metadata, dict)  # nosec - Silence mypy.

        for k, v in metadata.items():
            if v is None:
                print(f"{k}")
            else:
                value = repr(v)[2:][:-1]
                print(f"{k}: {value}")

        return 0
    except KeyboardInterrupt:  # pragma: no cover
        return 1


def main() -> int:
    """Entrypoint function for when the module is executed directly.

    :return: Exit status for the program.
    """

    if sys.executable:
        interpreter = os.path.basename(sys.executable)
    else:
        interpreter = "python3"

    parser = argparse.ArgumentParser(prog=f"{interpreter} -m aiotus")
    parser.add_argument("--debug", action="store_true", help="log debug messages")
    subparsers = parser.add_subparsers()

    parser_upload = subparsers.add_parser(
        "upload",
        help="Upload a file to a tus (tus.io) server.",
    )
    parser_upload.add_argument(
        "--metadata",
        action="append",
        default=[],
        help="additional metadata to upload ('key[=value]')",
    )
    parser_upload.add_argument(
        "endpoint", type=str, help="creation URL of the tus server"
    )
    parser_upload.add_argument("file", type=str, help="file to upload")
    parser_upload.set_defaults(func=_upload)

    parser_metadata = subparsers.add_parser(
        "metadata",
        help="Query the metadata of a file on a tus (tus.io) server.",
    )
    parser_metadata.add_argument(
        "location", type=str, help="file location on the tus server"
    )
    parser_metadata.set_defaults(func=_metadata)

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    return args.func(args)  # type: ignore
