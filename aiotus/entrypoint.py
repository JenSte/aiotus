import argparse
import asyncio
import logging
import mimetypes
import os.path

import aiotus


def aiotus_upload() -> int:
    """Entry point for the 'aiotus-upload' tool.

    :return: Exit status for the program.
    """

    parser = argparse.ArgumentParser(
        description="Tool to upload a file to a tus (tus.io) server.",
        epilog="This program is part of the aiotus python package.",
    )
    parser.add_argument("--debug", action="store_true", help="log debug messages")
    parser.add_argument(
        "--metadata",
        action="append",
        help="additional metadata to upload ('key[=value]')",
    )
    parser.add_argument("endpoint", type=str, help="creation URL of the tus server")
    parser.add_argument("file", type=str, help="file to upload")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    metadata = {"filename": os.path.basename(args.file).encode()}

    mime_type, _ = mimetypes.guess_type(args.file)
    if mime_type:
        metadata["mime_type"] = mime_type.encode()

    if args.metadata:
        for meta in args.metadata:
            kv = meta.split("=", maxsplit=1)
            metadata[kv[0]] = kv[1].encode() if (len(kv) == 2) else None

    try:
        with open(args.file, "rb") as file:
            location = asyncio.run(aiotus.upload(args.endpoint, file, metadata))
            if location:
                print(str(location))
                return 0
    except KeyboardInterrupt:  # pragma: no cover
        pass
    except Exception as e:
        logging.error(f"Unable to upload file: {e}")

    return 1


def aiotus_metadata() -> int:
    """Entry point for the 'aiotus-metadata' tool.

    :return: Exit status for the program.
    """

    parser = argparse.ArgumentParser(
        description="Tool to query the metadata of a file on a tus (tus.io) server.",
        epilog="This program is part of the aiotus python package.",
    )
    parser.add_argument("--debug", action="store_true", help="log debug messages")
    parser.add_argument("location", type=str, help="file location on the tus server")
    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    try:
        metadata = asyncio.run(aiotus.metadata(args.location))
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
