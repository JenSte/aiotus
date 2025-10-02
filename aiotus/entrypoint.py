"""Defines the commands for executing the module directly."""

from __future__ import annotations

import argparse
import asyncio
import logging
import mimetypes
import pathlib
import sys

from . import retry


def _upload(args: argparse.Namespace) -> int:
    """Implement the "upload" command.

    Returns the exit status for the program.
    """
    metadata: dict[str, bytes | None] = {
        "filename": pathlib.Path(args.file).name.encode()
    }

    if mime_type := mimetypes.guess_type(args.file)[0]:
        metadata["mime_type"] = mime_type.encode()

    for meta in args.metadata:
        kv = meta.split("=", maxsplit=1)
        metadata[kv[0]] = kv[1].encode() if (len(kv) == 2) else None  # noqa: PLR2004

    try:
        with pathlib.Path(args.file).open("rb") as file:
            if location := asyncio.run(retry.upload(args.endpoint, file, metadata)):
                print(str(location))  # noqa: T201
                return 0
    except KeyboardInterrupt:  # pragma: no cover
        pass
    except Exception as e:  # noqa: BLE001
        logging.error("Unable to upload file: %s", e)  # noqa: LOG015 TRY400

    return 1


def _metadata(args: argparse.Namespace) -> int:
    """Implement the "metadata" command.

    Returns the exit status for the program.
    """
    try:
        metadata = asyncio.run(retry.metadata(args.location))
        # Silence mypy, it does not detect the type 'asyncio.run()' returns.
        assert isinstance(metadata, dict)  # noqa: S101

        for k, v in metadata.items():
            if v is None:
                print(f"{k}")  # noqa: T201
            else:
                value = repr(v)[2:][:-1]
                print(f"{k}: {value}")  # noqa: T201
    except KeyboardInterrupt:  # pragma: no cover
        return 1

    return 0


def main() -> int:
    """Entrypoint function for when the module is executed directly.

    :return: Exit status for the program.
    """
    interpreter = pathlib.Path(sys.executable).name if sys.executable else "python3"

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

    if not hasattr(args, "func"):
        sys.stderr.write("No command specified.\n\n")
        parser.print_help(file=sys.stderr)
        return 1

    return args.func(args)  # type: ignore[no-any-return]
