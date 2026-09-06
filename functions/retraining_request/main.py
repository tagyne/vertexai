"""Turn Model Monitoring Pub/Sub alerts into approval requests."""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import functions_framework
from google.cloud import storage


def request_object_name(event_id: str) -> str:
    """Return the stable GCS object name used for an alert event."""
    safe_event_id = "".join(character for character in event_id if character.isalnum() or character in "-_.")
    if not safe_event_id:
        raise ValueError("event_id must contain at least one safe character")
    return f"monitoring/retraining-requests/{safe_event_id}.json"


def build_retraining_request(event_id: str, alert: dict[str, Any]) -> dict[str, Any]:
    """Build a serializable, human-reviewable retraining request."""
    return {
        "event_id": event_id,
        "status": "PENDING_APPROVAL",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "alert": alert,
    }


def _decode_alert(cloud_event: Any) -> tuple[str, dict[str, Any]]:
    event_id = str(cloud_event.get("id", ""))
    if not event_id:
        raise ValueError("CloudEvent is missing id")
    event_data = getattr(cloud_event, "data", cloud_event.get("data", {}))
    message = event_data.get("message", {})
    encoded_data = message.get("data", "")
    if not encoded_data:
        raise ValueError("Pub/Sub message is missing data")
    alert = json.loads(base64.b64decode(encoded_data).decode("utf-8"))
    if not isinstance(alert, dict):
        raise ValueError("Decoded monitoring alert must be a JSON object")
    return event_id, alert


@functions_framework.cloud_event
def handle_retraining_request(cloud_event: Any) -> None:
    """Persist one pending approval request; duplicate deliveries are ignored."""
    event_id, alert = _decode_alert(cloud_event)
    bucket_name = os.environ["RETRAINING_REQUEST_BUCKET"]
    request = build_retraining_request(event_id, alert)
    blob = storage.Client().bucket(bucket_name).blob(request_object_name(event_id))
    try:
        blob.upload_from_string(
            json.dumps(request), content_type="application/json", if_generation_match=0
        )
    except Exception as error:
        from google.api_core.exceptions import PreconditionFailed

        if isinstance(error, PreconditionFailed):
            logging.info("Ignoring duplicate monitoring alert %s", event_id)
            return
        raise
