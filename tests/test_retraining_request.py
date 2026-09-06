import json
import base64

from functions.retraining_request import main
from functions.retraining_request.main import build_retraining_request, request_object_name


def test_request_object_name_is_stable_for_an_alert_id() -> None:
    assert request_object_name("incident-123") == "monitoring/retraining-requests/incident-123.json"


def test_retraining_request_preserves_monitoring_alert_payload() -> None:
    alert = {"incident": {"condition_name": "feature drift", "state": "open"}}

    request = build_retraining_request("incident-123", alert)

    assert request["event_id"] == "incident-123"
    assert request["status"] == "PENDING_APPROVAL"
    assert request["alert"] == alert
    json.dumps(request)


def test_handler_persists_a_pending_request(monkeypatch) -> None:
    saved = {}

    class Blob:
        def upload_from_string(self, value, **kwargs):
            saved["value"] = json.loads(value)
            saved["kwargs"] = kwargs

    class Bucket:
        def blob(self, name):
            saved["name"] = name
            return Blob()

    class Client:
        def bucket(self, name):
            saved["bucket"] = name
            return Bucket()

    alert = {"incident": {"state": "open"}}
    event = {
        "id": "incident-123",
        "data": {"message": {"data": base64.b64encode(json.dumps(alert).encode()).decode()}},
    }
    monkeypatch.setenv("RETRAINING_REQUEST_BUCKET", "ml-bucket")
    monkeypatch.setattr(main.storage, "Client", Client)

    main.handle_retraining_request(event)

    assert saved["bucket"] == "ml-bucket"
    assert saved["name"] == "monitoring/retraining-requests/incident-123.json"
    assert saved["value"]["status"] == "PENDING_APPROVAL"
    assert saved["kwargs"]["if_generation_match"] == 0
