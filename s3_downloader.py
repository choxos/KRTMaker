from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Generator, Iterable, List, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from boto3.s3.transfer import S3Transfer


BIO_RXIV_BUCKET = "biorxiv-src-monthly"
BIO_RXIV_REGION = "us-east-1"


@dataclass
class S3ObjectSummary:
    key: str
    size: int
    etag: str


def build_s3_client(region_name: str = BIO_RXIV_REGION):
    return boto3.client(
        "s3",
        region_name=region_name,
        config=Config(signature_version="s3v4"),
    )


def list_objects(
    bucket: str = BIO_RXIV_BUCKET,
    prefix: str = "",
    max_keys: Optional[int] = None,
) -> Generator[S3ObjectSummary, None, None]:
    s3 = build_s3_client()

    kwargs = {
        "Bucket": bucket,
        "Prefix": prefix,
        "MaxKeys": max_keys or 1000,
    }

    # Some SDKs require RequestPayer for requester pays; if not accepted, retry without.
    include_request_payer = True
    continuation_token: Optional[str] = None

    while True:
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        try:
            if include_request_payer:
                response = s3.list_objects_v2(RequestPayer="requester", **kwargs)
            else:
                response = s3.list_objects_v2(**kwargs)
        except TypeError:
            include_request_payer = False
            response = s3.list_objects_v2(**kwargs)

        for obj in response.get("Contents", []) or []:
            yield S3ObjectSummary(
                key=obj["Key"], size=obj.get("Size", 0), etag=obj.get("ETag", "")
            )

        if response.get("IsTruncated"):
            continuation_token = response.get("NextContinuationToken")
        else:
            break


def download_objects(
    keys: Iterable[str],
    out_dir: str,
    bucket: str = BIO_RXIV_BUCKET,
) -> List[str]:
    s3 = build_s3_client()
    transfer = S3Transfer(s3)
    os.makedirs(out_dir, exist_ok=True)
    local_paths: List[str] = []
    for key in keys:
        local_path = os.path.join(out_dir, os.path.basename(key))
        try:
            transfer.download_file(
                bucket,
                key,
                local_path,
                extra_args={"RequestPayer": "requester"},
            )
            local_paths.append(local_path)
        except ClientError as e:
            raise RuntimeError(f"Failed to download s3://{bucket}/{key}: {e}") from e
    return local_paths
