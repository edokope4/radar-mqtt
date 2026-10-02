from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


def app_dir() -> Path:
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home()
    return root / "RadarMqtt"


CONFIG_PATH = app_dir() / "config.json"


@dataclass
class Topic:
    name: str
    enabled: bool = True


@dataclass
class Broker:
    id: str
    name: str
    host: str
    port: int = 1883
    username: str = ""
    password: str = ""
    tls: bool = False
    client_id: str = "radar-mqtt"
    topics: list[Topic] = field(default_factory=lambda: [Topic("cafetera/hacer")])
    qos: int = 0


@dataclass
class SavedPayload:
    id: str
    name: str
    body: str


@dataclass
class Settings:
    brokers: list[Broker] = field(default_factory=list)
    payloads: list[SavedPayload] = field(default_factory=list)
    selected_broker_id: str = ""
    only_saved_payloads: bool = False


def default_settings() -> Settings:
    broker_id = str(uuid.uuid4())
    return Settings(
        brokers=[
            Broker(
                id=broker_id,
                name="Mosquitto test",
                host="test.mosquitto.org",
                port=1883,
                topics=[Topic("cafetera/hacer")],
                qos=0,
                client_id="radar-mqtt",
            )
        ],
        payloads=[
            SavedPayload(id=str(uuid.uuid4()), name="Hacer café", body="hacer"),
        ],
        selected_broker_id=broker_id,
    )


def _topic_from_raw(item: object) -> Topic | None:
    if isinstance(item, str):
        name = item.strip()
        return Topic(name) if name else None
    if isinstance(item, dict):
        name = str(item.get("name") or "").strip()
        if not name:
            return None
        return Topic(name, bool(item.get("enabled", True)))
    return None


def topics_from_raw(raw: object) -> list[Topic]:
    items = raw if isinstance(raw, list) else []
    topics = [topic for item in items if (topic := _topic_from_raw(item)) is not None]
    return topics or [Topic("cafetera/hacer")]


def enabled_topic_names(topics: list[Topic]) -> list[str]:
    return [topic.name for topic in topics if topic.enabled and topic.name.strip()]


def _broker_from_dict(raw: dict) -> Broker:
    topics = topics_from_raw(raw.get("topics"))
    return Broker(
        id=str(raw.get("id") or uuid.uuid4()),
        name=str(raw.get("name") or "Broker"),
        host=str(raw.get("host") or "").strip(),
        port=int(raw.get("port") or 1883),
        username=str(raw.get("username") or ""),
        password=str(raw.get("password") or ""),
        tls=bool(raw.get("tls")),
        client_id=str(raw.get("client_id") or "radar-mqtt"),
        topics=topics,
        qos=max(0, min(2, int(raw.get("qos") or 0))),
    )


def _payload_from_dict(raw: dict) -> SavedPayload:
    body = str(raw.get("body") or "")
    name = str(raw.get("name") or body or "Payload")
    return SavedPayload(id=str(raw.get("id") or uuid.uuid4()), name=name, body=body)


def load_settings() -> Settings:
    path = app_dir() / "config.json"
    if not path.exists():
        settings = default_settings()
        save_settings(settings)
        return settings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_settings()

    brokers = [_broker_from_dict(item) for item in raw.get("brokers", []) if isinstance(item, dict)]
    payloads = [
        _payload_from_dict(item)
        for item in raw.get("payloads", [])
        if isinstance(item, dict) and str(item.get("body") or "").strip()
    ]
    settings = Settings(
        brokers=brokers,
        payloads=payloads,
        selected_broker_id=str(raw.get("selected_broker_id") or ""),
        only_saved_payloads=bool(raw.get("only_saved_payloads")),
    )
    if settings.selected_broker_id not in {broker.id for broker in settings.brokers}:
        settings.selected_broker_id = settings.brokers[0].id if settings.brokers else ""
    return settings


def save_settings(settings: Settings) -> None:
    folder = app_dir()
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "brokers": [asdict(broker) for broker in settings.brokers],
        "payloads": [asdict(item) for item in settings.payloads],
        "selected_broker_id": settings.selected_broker_id,
        "only_saved_payloads": settings.only_saved_payloads,
    }
    target = folder / "config.json"
    temporary = folder / "config.json.tmp"
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def match_payload(text: str, payloads: list[SavedPayload]) -> SavedPayload | None:
    stripped = text.strip()
    for item in payloads:
        if item.body.strip() == stripped:
            return item
    return None
