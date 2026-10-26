"""Record validated S3 creation-event metadata in DynamoDB, with deduplication."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote_plus


def normalise_record(record):
    if not isinstance(record, dict) or record.get("eventSource") != "aws:s3":
        raise ValueError("Expected an S3 event record.")
    event_name = record.get("eventName", "")
    if not isinstance(event_name, str) or not event_name.startswith("ObjectCreated:"):
        raise ValueError("Only S3 object-creation events are supported.")
    try:
        bucket, obj = record["s3"]["bucket"]["name"], record["s3"]["object"]
        encoded_key, size, sequence = obj["key"], obj["size"], obj["sequencer"]
    except (KeyError, TypeError) as exc:
        raise ValueError("The event is missing required S3 metadata.") from exc
    if not isinstance(bucket, str) or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket):
        raise ValueError("Invalid bucket name.")
    if not isinstance(encoded_key, str) or not encoded_key or re.search(r"%(?![0-9a-fA-F]{2})", encoded_key):
        raise ValueError("Object keys must use valid URL encoding.")
    try:
        key = unquote_plus(encoded_key, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Object key must be valid UTF-8.") from exc
    if not key or len(key.encode("utf-8")) > 1024:
        raise ValueError("Object key must contain 1 to 1024 UTF-8 bytes.")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ValueError("Object size must be a nonnegative integer.")
    if not isinstance(sequence, str) or not re.fullmatch(r"[A-Fa-f0-9]+", sequence):
        raise ValueError("The event needs a hexadecimal sequencer.")
    version = obj.get("versionId", "")
    if not isinstance(version, str):
        raise ValueError("Version ID must be text when present.")
    identity = {"bucket": bucket, "key": key, "version": version,
                "sequence": sequence.lstrip("0").lower() or "0", "event_name": event_name}
    event_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return {"event_id": event_id, **identity, "size_bytes": size}


def parse_event(event):
    if not isinstance(event, dict) or not isinstance(event.get("Records"), list) or not event["Records"]:
        raise ValueError("Expected a nonempty Records list.")
    # Validate the whole batch before the first external write.
    return [normalise_record(record) for record in event["Records"]]


def item_for(record):
    return {"pk": {"S": record["event_id"]}, "bucket": {"S": record["bucket"]},
            "object_key": {"S": record["key"]}, "version": {"S": record["version"]},
            "sequencer": {"S": record["sequence"]}, "size_bytes": {"N": str(record["size_bytes"])},
            "event_name": {"S": record["event_name"]}}


def process_event(event, client, table_name):
    from botocore.exceptions import ClientError
    if not isinstance(table_name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{3,255}", table_name):
        raise ValueError("A valid DynamoDB table name is required.")
    records = parse_event(event)
    written = duplicates = 0
    for record in records:
        try:
            client.put_item(TableName=table_name, Item=item_for(record),
                            ConditionExpression="attribute_not_exists(pk)")
            written += 1
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            duplicates += 1
    return {"received": len(records), "written": written, "duplicates": duplicates}


def handler(event, context):
    table_name = os.environ.get("TABLE_NAME", "")
    if not table_name:
        raise ValueError("TABLE_NAME is not configured.")
    parse_event(event)
    import boto3
    return process_event(event, boto3.client("dynamodb"), table_name)


if __name__ == "__main__":
    source = Path(__file__).resolve().parents[1] / "sample-event.json"
    print(json.dumps({"mode": "offline metadata preview; no AWS requests",
                      "records": parse_event(json.loads(source.read_text()))}, indent=2))
