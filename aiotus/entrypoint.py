#!/usr/bin/env python3

import argparse
import asyncio
import logging
import mimetypes
import os.path
from typing import Optional

import aiotus


async def aiotus_upload_coro(
    args: argparse.Namespace, metadata: aiotus.Metadata
) -> Optional[str]:
    with open(args.file, "rb") as file:
        location = await aiotus.upload(args.endpoint, file, metadata)

    if location:
        print(str(location))
        return str(location)

    return None


def aiotus_upload() -> int:
    parser = argparse.ArgumentParser(
        description="Tool to upload a file to a tus (tus.io) server.",
        epilog="This program is part of the aiotus python package.",
    )
    parser.add_argument("--debug", action="store_true", help="log debug messages")
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

    try:
        location = asyncio.run(aiotus_upload_coro(args, metadata))
        return 1 if (location is None) else 0
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Unable to upload file: {e}")

    return 1


def aiotus_metadata() -> int:
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

        if metadata:
            for k, v in metadata.items():
                if v is None:
                    print(f"{k}")
                else:
                    value = repr(v)[2:][:-1]
                    print(f"{k}: {value}")

        return 0
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Unable to fetch metadata: {e}")

    return 1
