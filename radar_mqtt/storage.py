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
class FavoriteMessage:
    id: str
    name: str
    broker_id: str
    topic: str
    body: str
    qos: int = 0
    retain: bool = False


@dataclass
class Settings:
    brokers: list[Broker] = field(default_factory=list)
    payloads: list[SavedPayload] = field(default_factory=list)
    favorites: list[FavoriteMessage] = field(default_factory=list)
    selected_broker_id: str = ""
    only_saved_payloads: bool = False
    dark: bool = True


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


def _favorite_from_dict(raw: dict) -> FavoriteMessage | None:
    topic = str(raw.get("topic") or "").strip()
    name = str(raw.get("name") or topic or "Favorito").strip()
    if not topic or not name:
        return None
    try:
        qos = int(raw.get("qos") or 0)
    except (TypeError, ValueError):
        qos = 0
    return FavoriteMessage(
        id=str(raw.get("id") or uuid.uuid4()),
        name=name,
        broker_id=str(raw.get("broker_id") or ""),
        topic=topic,
        body=str(raw.get("body") or ""),
        qos=max(0, min(2, qos)),
        retain=bool(raw.get("retain")),
    )


def settings_document(settings: Settings) -> dict:
    return {
        "brokers": [asdict(broker) for broker in settings.brokers],
        "payloads": [asdict(item) for item in settings.payloads],
        "favorites": [asdict(item) for item in settings.favorites],
        "selected_broker_id": settings.selected_broker_id,
        "only_saved_payloads": settings.only_saved_payloads,
        "dark": settings.dark,
    }


def settings_from_document(raw: object) -> Settings:
    if not isinstance(raw, dict):
        raise ValueError("El archivo no tiene una configuración válida.")
    brokers_raw = raw.get("brokers")
    if not isinstance(brokers_raw, list) or not brokers_raw:
        raise ValueError("El archivo no incluye brokers.")
    brokers: list[Broker] = []
    for item in brokers_raw:
        if not isinstance(item, dict):
            raise ValueError("El archivo no tiene una configuración válida.")
        broker = _broker_from_dict(item)
        if not broker.host:
            raise ValueError("Un broker del archivo no tiene host.")
        brokers.append(broker)
    payloads_raw = raw.get("payloads", [])
    if not isinstance(payloads_raw, list):
        raise ValueError("El archivo no tiene una configuración válida.")
    payloads = [
        _payload_from_dict(item)
        for item in payloads_raw
        if isinstance(item, dict) and str(item.get("body") or "").strip()
    ]
    favorites_raw = raw.get("favorites", [])
    if not isinstance(favorites_raw, list):
        raise ValueError("El archivo no tiene una configuración válida.")
    favorites = [
        favorite
        for item in favorites_raw
        if isinstance(item, dict) and (favorite := _favorite_from_dict(item)) is not None
    ]
    settings = Settings(
        brokers=brokers,
        payloads=payloads,
        favorites=favorites,
        selected_broker_id=str(raw.get("selected_broker_id") or ""),
        only_saved_payloads=bool(raw.get("only_saved_payloads")),
        dark=bool(raw.get("dark", True)),
    )
    if settings.selected_broker_id not in {broker.id for broker in settings.brokers}:
        settings.selected_broker_id = settings.brokers[0].id
    return settings


def load_settings() -> Settings:
    path = app_dir() / "config.json"
    if not path.exists():
        settings = default_settings()
        save_settings(settings)
        return settings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return settings_from_document(raw)
    except (OSError, json.JSONDecodeError, ValueError):
        return default_settings()


def save_settings(settings: Settings) -> None:
    folder = app_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "config.json"
    temporary = folder / "config.json.tmp"
    temporary.write_text(
        json.dumps(settings_document(settings), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(target)


def match_payload(text: str, payloads: list[SavedPayload]) -> SavedPayload | None:
    stripped = text.strip()
    for item in payloads:
        if item.body.strip() == stripped:
            return item
    return None
