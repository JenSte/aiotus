#!/usr/bin/env python3

import argparse
import asyncio
import logging
import mimetypes
import os.path
from typing import Dict, Optional

import aiotus


async def aiotus_client_coro(
    args: argparse.Namespace, metadata: Dict[str, str]
) -> Optional[str]:
    with open(args.file, "rb") as file:
        location = await aiotus.upload(args.endpoint, file, metadata)

    if location:
        logging.info(f'File uploaded to "{location}".')
        return str(location)

    return None


def aiotus_client() -> int:
    parser = argparse.ArgumentParser(
        description="tus (tus.io) client from the aiotus python package."
    )
    parser.add_argument("endpoint", type=str, help="creation URL of the tus server")
    parser.add_argument("file", type=str, help="file to upload")
    args = parser.parse_args()

    metadata = {"filename": os.path.basename(args.file)}

    mime_type, _ = mimetypes.guess_type(args.file)
    if mime_type:
        metadata["mime_type"] = mime_type

    logging.basicConfig(level=logging.INFO)

    try:
        location = asyncio.run(aiotus_client_coro(args, metadata))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Unable to upload file: {e}")
        return 1

    return 1 if (location is None) else 0
