from __future__ import annotations

import ctypes
import json
import os
import queue
import threading
import uuid
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import paho.mqtt.client as mqtt

from radar_mqtt.storage import (
    Broker,
    Settings,
    Topic,
    enabled_topic_names,
    load_settings,
    match_payload,
    save_settings,
    settings_document,
    settings_from_document,
)

BG = "#F6F3EF"
INK = "#2C211C"
MUTED = "#8A7568"
BROWN = "#6F4E37"
BROWN_DARK = "#5C3A2E"
OK = "#2E7D4F"
WARN = "#C47A3A"
ERROR = "#A33B32"
JSON_KEY = "#6F4E37"
JSON_STR = "#1B7A4E"
JSON_NUM = "#B86E2A"
JSON_BOOL = "#3E6B9A"
JSON_NULL = "#8A7568"


def pretty_json(text: str) -> str | None:
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return None
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def json_tokens(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char in " \n\t":
            end = index + 1
            while end < length and text[end] in " \n\t":
                end += 1
            tokens.append(("", text[index:end]))
            index = end
            continue
        if char in "{}[],:":
            tokens.append(("json_punct", char))
            index += 1
            continue
        if char == '"':
            end = index + 1
            while end < length:
                if text[end] == "\\":
                    end += 2
                    continue
                if text[end] == '"':
                    end += 1
                    break
                end += 1
            look = end
            while look < length and text[look] in " \n\t":
                look += 1
            tag = "json_key" if look < length and text[look] == ":" else "json_str"
            tokens.append((tag, text[index:end]))
            index = end
            continue
        if char == "-" or char.isdigit():
            end = index + 1
            while end < length and text[end] in "0123456789.eE+-":
                end += 1
            tokens.append(("json_num", text[index:end]))
            index = end
            continue
        matched_word = False
        for word, tag in (("true", "json_bool"), ("false", "json_bool"), ("null", "json_null")):
            if text.startswith(word, index):
                tokens.append((tag, word))
                index += len(word)
                matched_word = True
                break
        if not matched_word:
            tokens.append(("", char))
            index += 1
    return tokens


def enable_dpi() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        return


class RadarApp:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.events: queue.Queue[tuple] = queue.Queue()
        self.client: mqtt.Client | None = None
        self._client_lock = threading.Lock()
        self.listening = False
        self._user_stop = False
        self._active_topics: list[str] = []
        self._active_qos = 0
        self._message_count = 0
        self._draft_id = ""
        self._copy_buttons: list[tk.Button] = []
        self._publish_broker_id = ""
        self._publishing = False

        self.root = tk.Tk()
        self.root.title("Radar MQTT")
        self.root.geometry("1040x740")
        self.root.minsize(900, 640)
        self.root.configure(bg=BG)
        self._style()
        self._build()
        self._load_initial()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(150, self._poll)

    def run(self) -> None:
        self.root.mainloop()

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), background=BG)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("TLabelframe", background=BG, foreground=BROWN)
        style.configure("TLabelframe.Label", background=BG, foreground=BROWN, font=("Segoe UI", 11, "bold"))
        style.configure("TButton", padding=(10, 6))
        style.configure("TCheckbutton", background=BG, foreground=INK)
        style.configure("TEntry", padding=4)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(header, text="Radar MQTT", bg=BG, fg=INK, font=("Segoe UI", 20, "bold")).pack(side="left")
        self.status_label = tk.Label(header, text="Detenido", bg=BG, fg=MUTED, font=("Segoe UI", 11))
        self.status_label.pack(side="right", padx=(12, 0))
        self.notice_label = tk.Label(header, text="", bg=BG, fg=OK, font=("Segoe UI", 10))
        self.notice_label.pack(side="right")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=False, padx=16, pady=4)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        self._build_broker(body)
        self._build_publish(body)
        self._build_listen_bar()
        self._build_log()

    def _build_broker(self, parent: tk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Brokers", padding=12)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Guardados").grid(row=0, column=0, sticky="w")
        self.broker_combo = ttk.Combobox(frame, state="readonly")
        self.broker_combo.grid(row=0, column=1, sticky="ew", padx=8)
        self.broker_combo.bind("<<ComboboxSelected>>", self._on_broker_selected)
        ttk.Button(frame, text="Nuevo", command=self.new_broker).grid(row=0, column=2)

        self.name_var = tk.StringVar()
        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar(value="1883")
        self.user_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.client_var = tk.StringVar(value="radar-mqtt")
        self.qos_var = tk.StringVar(value="0")
        self.tls_var = tk.BooleanVar(value=False)

        fields = [
            (1, "Nombre", self.name_var),
            (2, "Host", self.host_var),
            (3, "Usuario", self.user_var),
            (4, "Contraseña", self.password_var),
            (5, "Client ID", self.client_var),
        ]
        self._entries: list[ttk.Entry] = []
        for row, label, variable in fields:
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(frame, textvariable=variable)
            if label == "Contraseña":
                entry.configure(show="*")
            entry.grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
            self._entries.append(entry)

        extra = tk.Frame(frame, bg=BG)
        extra.grid(row=6, column=0, columnspan=3, sticky="ew", pady=4)
        ttk.Label(extra, text="Puerto").pack(side="left")
        self.port_entry = ttk.Entry(extra, textvariable=self.port_var, width=8)
        self.port_entry.pack(side="left", padx=(8, 16))
        ttk.Label(extra, text="QoS").pack(side="left")
        self.qos_entry = ttk.Spinbox(extra, from_=0, to=2, textvariable=self.qos_var, width=4)
        self.qos_entry.pack(side="left", padx=(8, 16))
        self.tls_check = ttk.Checkbutton(extra, text="TLS", variable=self.tls_var)
        self.tls_check.pack(side="left")

        ttk.Label(frame, text="Tópicos").grid(row=7, column=0, sticky="w", pady=(8, 2))
        ttk.Label(frame, text="Desmarcá para no escuchar", style="Muted.TLabel").grid(
            row=7, column=1, columnspan=2, sticky="e", pady=(8, 2)
        )
        holder = tk.Frame(frame, bg="white", highlightbackground="#E4DDD6", highlightthickness=1)
        holder.grid(row=8, column=0, columnspan=3, sticky="ew")
        holder.columnconfigure(0, weight=1)
        self.topics_canvas = tk.Canvas(holder, height=88, bg="white", highlightthickness=0)
        self.topics_canvas.grid(row=0, column=0, sticky="ew")
        topics_scroll = ttk.Scrollbar(holder, orient="vertical", command=self.topics_canvas.yview)
        topics_scroll.grid(row=0, column=1, sticky="ns")
        self.topics_canvas.configure(yscrollcommand=topics_scroll.set)
        self.topics_list = tk.Frame(self.topics_canvas, bg="white")
        self._topics_window = self.topics_canvas.create_window((0, 0), window=self.topics_list, anchor="nw")
        self.topics_list.bind("<Configure>", self._fit_topics)
        self.topics_canvas.bind("<Configure>", self._fit_topics_width)
        self.topics_canvas.bind("<Enter>", self._bind_topics_wheel)
        self.topics_canvas.bind("<Leave>", self._unbind_topics_wheel)
        self._topic_rows: list[tuple[tk.Frame, str, tk.BooleanVar, ttk.Checkbutton, tk.Button]] = []

        add = tk.Frame(frame, bg=BG)
        add.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        add.columnconfigure(0, weight=1)
        self.topic_var = tk.StringVar()
        self.topic_entry = ttk.Entry(add, textvariable=self.topic_var)
        self.topic_entry.grid(row=0, column=0, sticky="ew")
        self.topic_entry.bind("<Return>", lambda _event: self.add_topic())
        self.add_topic_button = ttk.Button(add, text="Agregar", command=self.add_topic)
        self.add_topic_button.grid(row=0, column=1, padx=(8, 0))

        actions = tk.Frame(frame, bg=BG)
        actions.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.save_broker_button = ttk.Button(actions, text="Guardar broker", command=self.save_broker)
        self.save_broker_button.pack(side="left")
        self.delete_broker_button = ttk.Button(actions, text="Eliminar", command=self.delete_broker)
        self.delete_broker_button.pack(side="left", padx=8)
        ttk.Label(actions, text="1883 sin TLS, 8883 con TLS", style="Muted.TLabel").pack(side="right")

        files = tk.Frame(frame, bg=BG)
        files.grid(row=11, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(files, text="Exportar", command=self.export_settings).pack(side="left")
        ttk.Button(files, text="Importar", command=self.import_settings).pack(side="left", padx=8)

    def _build_publish(self, parent: tk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Publicar", padding=12)
        frame.grid(row=0, column=1, sticky="nsew")
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

        ttk.Label(frame, text="Broker").grid(row=0, column=0, sticky="w", pady=4)
        self.publish_broker_combo = ttk.Combobox(frame, state="readonly")
        self.publish_broker_combo.grid(row=0, column=1, sticky="ew", pady=4)
        self.publish_broker_combo.bind("<<ComboboxSelected>>", self._on_publish_broker)

        ttk.Label(frame, text="Tópico").grid(row=1, column=0, sticky="w", pady=4)
        self.publish_topic_var = tk.StringVar()
        self.publish_topic_entry = ttk.Entry(frame, textvariable=self.publish_topic_var)
        self.publish_topic_entry.grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="QoS").grid(row=2, column=0, sticky="w", pady=4)
        qos_row = tk.Frame(frame, bg=BG)
        qos_row.grid(row=2, column=1, sticky="ew", pady=4)
        self.publish_qos_var = tk.StringVar(value="0")
        self.publish_qos_entry = ttk.Spinbox(qos_row, from_=0, to=2, textvariable=self.publish_qos_var, width=4)
        self.publish_qos_entry.pack(side="left")
        self.publish_retain_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(qos_row, text="Retenido", variable=self.publish_retain_var).pack(side="left", padx=(16, 0))

        ttk.Label(frame, text="Payload").grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 2))
        self.publish_payload = tk.Text(
            frame,
            height=8,
            wrap="word",
            font=("Consolas", 10),
            bg="white",
            fg=INK,
            relief="flat",
            padx=6,
            pady=6,
        )
        self.publish_payload.grid(row=4, column=0, columnspan=2, sticky="nsew")

        self.publish_button = tk.Button(
            frame,
            text="Publicar",
            command=self.publish_message,
            bg=BROWN,
            fg="white",
            activebackground=BROWN_DARK,
            activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            padx=12,
            pady=6,
            cursor="hand2",
        )
        self.publish_button.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))

    def _build_listen_bar(self) -> None:
        bar = tk.Frame(self.root, bg=BG)
        bar.pack(fill="x", padx=16, pady=(8, 4))
        self.listen_button = tk.Button(
            bar,
            text="Comenzar a escuchar",
            command=self.toggle_listen,
            bg=BROWN,
            fg="white",
            activebackground=BROWN_DARK,
            activeforeground="white",
            font=("Segoe UI", 12, "bold"),
            relief="flat",
            padx=18,
            pady=8,
            cursor="hand2",
        )
        self.listen_button.pack(fill="x")

    def _build_log(self) -> None:
        frame = ttk.LabelFrame(self.root, text="Mensajes", padding=12)
        frame.pack(fill="both", expand=True, padx=16, pady=(4, 14))
        frame.rowconfigure(1, weight=1)
        frame.columnconfigure(0, weight=1)

        top = tk.Frame(frame, bg=BG)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.count_label = tk.Label(top, text="0 mensajes", bg=BG, fg=MUTED, font=("Segoe UI", 10))
        self.count_label.pack(side="left")
        ttk.Button(top, text="Limpiar", command=self.clear_log).pack(side="right")

        self.log = tk.Text(
            frame,
            height=12,
            wrap="char",
            font=("Consolas", 10),
            bg="white",
            fg=INK,
            relief="flat",
            padx=8,
            pady=8,
            cursor="xterm",
        )
        self.log.grid(row=1, column=0, sticky="nsew")
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=self.log.yview)
        scroll_y.grid(row=1, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll_y.set)
        self.log.bind("<Key>", self._guard_log)
        self.log.bind("<Control-a>", self._select_all_log)
        self.log.bind("<Control-A>", self._select_all_log)
        self.log.bind("<Button-3>", self._show_log_menu)
        self._log_menu = tk.Menu(self.log, tearoff=0)
        self._log_menu.add_command(label="Copiar", command=self._copy_log)
        self._log_menu.add_command(label="Seleccionar todo", command=self._select_all_log)
        self.log.tag_configure("match", foreground=OK, font=("Consolas", 10, "bold"))
        self.log.tag_configure("info", foreground=BROWN)
        self.log.tag_configure("error", foreground=ERROR)
        self.log.tag_configure("msg", foreground=INK)
        self.log.tag_configure("json_key", foreground=JSON_KEY, font=("Consolas", 10, "bold"))
        self.log.tag_configure("json_str", foreground=JSON_STR)
        self.log.tag_configure("json_num", foreground=JSON_NUM)
        self.log.tag_configure("json_bool", foreground=JSON_BOOL, font=("Consolas", 10, "bold"))
        self.log.tag_configure("json_null", foreground=JSON_NULL, font=("Consolas", 10, "italic"))
        self.log.tag_configure("json_punct", foreground=INK)

    def _load_initial(self) -> None:
        self._publish_broker_id = self.settings.selected_broker_id
        self._refresh_brokers()
        selected = self._broker_by_id(self.settings.selected_broker_id)
        if selected:
            self._select_broker(selected)
        elif self.settings.brokers:
            self._select_broker(self.settings.brokers[0])
        else:
            self.new_broker()

    def _broker_by_id(self, broker_id: str) -> Broker | None:
        for broker in self.settings.brokers:
            if broker.id == broker_id:
                return broker
        return None

    def _broker_label(self, broker: Broker) -> str:
        return f"{broker.name}   ·   {broker.host}:{broker.port}"

    def _refresh_brokers(self) -> None:
        labels = [self._broker_label(broker) for broker in self.settings.brokers]
        self.broker_combo.configure(values=labels)
        current = self._broker_by_id(self.settings.selected_broker_id)
        if current and current in self.settings.brokers:
            self.broker_combo.current(self.settings.brokers.index(current))
        elif labels:
            self.broker_combo.current(0)
        self._refresh_publish_brokers()

    def _refresh_publish_brokers(self) -> None:
        labels = [self._broker_label(broker) for broker in self.settings.brokers]
        self.publish_broker_combo.configure(values=labels)
        if not self.settings.brokers:
            self.publish_broker_combo.set("")
            self._publish_broker_id = ""
            return
        selected = self._broker_by_id(self._publish_broker_id)
        if selected is None:
            selected = self.settings.brokers[0]
            self._publish_broker_id = selected.id
        self.publish_broker_combo.current(self.settings.brokers.index(selected))

    def _on_publish_broker(self, _event: object) -> None:
        index = self.publish_broker_combo.current()
        if index < 0 or index >= len(self.settings.brokers):
            return
        self._publish_broker_id = self.settings.brokers[index].id

    def _read_publish(self) -> tuple[Broker, str, str, int, bool]:
        broker = self._broker_by_id(self._publish_broker_id)
        if broker is None:
            raise ValueError("Elegí un broker guardado.")
        topic = self.publish_topic_var.get().strip()
        if not topic:
            raise ValueError("Escribí el tópico.")
        try:
            qos = int(self.publish_qos_var.get().strip())
        except ValueError:
            raise ValueError("El QoS tiene que ser 0, 1 o 2.") from None
        if qos not in (0, 1, 2):
            raise ValueError("El QoS tiene que ser 0, 1 o 2.")
        payload = self.publish_payload.get("1.0", "end-1c")
        return broker, topic, payload, qos, bool(self.publish_retain_var.get())

    def publish_message(self) -> None:
        if self._publishing:
            return
        try:
            broker, topic, payload, qos, retain = self._read_publish()
        except ValueError as error:
            messagebox.showwarning("Radar MQTT", str(error))
            return
        self._publishing = True
        self.publish_button.configure(state="disabled", text="Publicando…")
        threading.Thread(
            target=self._publish,
            args=(broker, topic, payload, qos, retain),
            daemon=True,
        ).start()

    def _publish(self, broker: Broker, topic: str, payload: str, qos: int, retain: bool) -> None:
        client_id = broker.client_id.strip() or "radar"
        client = self._build_client(broker, client_id=f"{client_id}-pub-{uuid.uuid4().hex[:6]}", listen=False)
        try:
            client.connect(broker.host, broker.port, keepalive=30)
            client.loop_start()
            info = client.publish(topic, payload.encode("utf-8"), qos=qos, retain=retain)
            info.wait_for_publish(timeout=10)
            if not info.is_published():
                self.events.put(("publish_failed", "El broker no confirmó la publicación."))
                return
            self.events.put(("published", broker.name, topic, retain))
        except Exception as error:
            detail = str(error).strip() or error.__class__.__name__
            self.events.put(("publish_failed", detail))
        finally:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass
            self.events.put(("publish_done",))

    def _fit_topics(self, _event: object = None) -> None:
        self.topics_canvas.configure(scrollregion=self.topics_canvas.bbox("all"))

    def _fit_topics_width(self, event: tk.Event) -> None:
        self.topics_canvas.itemconfigure(self._topics_window, width=event.width)

    def _bind_topics_wheel(self, _event: object) -> None:
        self.topics_canvas.bind_all("<MouseWheel>", self._scroll_topics)

    def _unbind_topics_wheel(self, _event: object) -> None:
        self.topics_canvas.unbind_all("<MouseWheel>")

    def _scroll_topics(self, event: tk.Event) -> None:
        self.topics_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _set_topics(self, topics: list[Topic]) -> None:
        for frame, _name, _var, _check, _remove in self._topic_rows:
            frame.destroy()
        self._topic_rows = []
        for topic in topics:
            self._add_topic_row(topic.name, topic.enabled)

    def _add_topic_row(self, name: str, enabled: bool) -> None:
        row = tk.Frame(self.topics_list, bg="white")
        row.pack(fill="x", padx=4, pady=1)
        variable = tk.BooleanVar(value=enabled)
        check = ttk.Checkbutton(row, variable=variable, command=lambda: self._toggle_topic(name))
        check.pack(side="left")
        label = tk.Label(row, text=name, bg="white", fg=INK if enabled else MUTED, anchor="w", font=("Segoe UI", 10))
        label.pack(side="left", fill="x", expand=True, padx=(4, 8))
        remove = tk.Button(
            row,
            text="×",
            command=lambda: self._remove_topic(name),
            bg="white",
            fg=MUTED,
            activebackground="white",
            activeforeground=ERROR,
            relief="flat",
            bd=0,
            padx=4,
            cursor="hand2",
        )
        remove.pack(side="right")
        variable.trace_add("write", lambda *_args: label.configure(fg=INK if variable.get() else MUTED))
        self._topic_rows.append((row, name, variable, check, remove))
        self._fit_topics()

    def _topics_from_rows(self) -> list[Topic]:
        return [Topic(name, bool(variable.get())) for _row, name, variable, _check, _remove in self._topic_rows]

    def _toggle_topic(self, _name: str) -> None:
        self._persist_topics()

    def _persist_topics(self) -> None:
        broker = self._broker_by_id(self._draft_id)
        if broker is None:
            return
        broker.topics = self._topics_from_rows()
        save_settings(self.settings)

    def add_topic(self) -> None:
        name = self.topic_var.get().strip()
        if not name:
            messagebox.showwarning("Radar MQTT", "Escribí el tópico.")
            return
        if any(current == name for _row, current, _variable, _check, _remove in self._topic_rows):
            messagebox.showwarning("Radar MQTT", "Ese tópico ya está en la lista.")
            return
        self._add_topic_row(name, True)
        self.topic_var.set("")
        self._persist_topics()

    def _remove_topic(self, name: str) -> None:
        kept = [(row, current, variable, check, remove) for row, current, variable, check, remove in self._topic_rows if current != name]
        for row, current, _variable, _check, _remove in self._topic_rows:
            if current == name:
                row.destroy()
        self._topic_rows = kept
        self._fit_topics()
        self._persist_topics()

    def _select_broker(self, broker: Broker) -> None:
        self.settings.selected_broker_id = broker.id
        self._draft_id = broker.id
        self.name_var.set(broker.name)
        self.host_var.set(broker.host)
        self.port_var.set(str(broker.port))
        self.user_var.set(broker.username)
        self.password_var.set(broker.password)
        self.client_var.set(broker.client_id)
        self.qos_var.set(str(broker.qos))
        self.tls_var.set(broker.tls)
        self._set_topics(broker.topics)
        self._refresh_brokers()

    def _on_broker_selected(self, _event: object) -> None:
        index = self.broker_combo.current()
        if index < 0 or index >= len(self.settings.brokers):
            return
        self._select_broker(self.settings.brokers[index])

    def new_broker(self) -> None:
        self._draft_id = str(uuid.uuid4())
        self.settings.selected_broker_id = ""
        self.broker_combo.set("")
        self.name_var.set("Nuevo broker")
        self.host_var.set("")
        self.port_var.set("1883")
        self.user_var.set("")
        self.password_var.set("")
        self.client_var.set("radar-mqtt")
        self.qos_var.set("0")
        self.tls_var.set(False)
        self._set_topics([Topic("cafetera/hacer")])
        self._notice("Completá el broker y guardalo, o empezá a escuchar.")

    def read_form(self) -> Broker:
        name = self.name_var.get().strip()
        host = self.host_var.get().strip()
        if not host:
            raise ValueError("Completá el host del broker.")
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            raise ValueError("El puerto no es válido.") from None
        if port < 1 or port > 65535:
            raise ValueError("El puerto tiene que estar entre 1 y 65535.")
        try:
            qos = int(self.qos_var.get().strip())
        except ValueError:
            raise ValueError("El QoS tiene que ser 0, 1 o 2.") from None
        if qos not in (0, 1, 2):
            raise ValueError("El QoS tiene que ser 0, 1 o 2.")
        topics = self._topics_from_rows()
        if not topics:
            raise ValueError("Agregá al menos un tópico.")
        broker_id = self._draft_id or self.settings.selected_broker_id or str(uuid.uuid4())
        self._draft_id = broker_id
        return Broker(
            id=broker_id,
            name=name or host,
            host=host,
            port=port,
            username=self.user_var.get(),
            password=self.password_var.get(),
            tls=bool(self.tls_var.get()),
            client_id=self.client_var.get().strip() or "radar-mqtt",
            topics=topics,
            qos=qos,
        )

    def _store_broker(self, broker: Broker) -> None:
        for index, current in enumerate(self.settings.brokers):
            if current.id == broker.id:
                self.settings.brokers[index] = broker
                break
        else:
            self.settings.brokers.append(broker)
        self.settings.selected_broker_id = broker.id
        save_settings(self.settings)
        self._refresh_brokers()

    def export_settings(self) -> None:
        try:
            broker = self.read_form()
        except ValueError:
            broker = None
        if broker is not None:
            self._store_broker(broker)
        path = filedialog.asksaveasfilename(
            title="Exportar configuración",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="radar-mqtt.json",
        )
        if not path:
            return
        document = json.dumps(settings_document(self.settings), ensure_ascii=False, indent=2)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(document + "\n")
        except OSError as error:
            messagebox.showerror("Radar MQTT", f"No se pudo guardar el archivo.\n{error}")
            return
        self._notice("Configuración exportada")

    def import_settings(self) -> None:
        path = filedialog.askopenfilename(
            title="Importar configuración",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        if not messagebox.askyesno("Radar MQTT", "Esto reemplaza los brokers guardados. ¿Continuar?"):
            return
        try:
            with open(path, encoding="utf-8") as handle:
                raw = json.load(handle)
            settings = settings_from_document(raw)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            detail = str(error).strip() or "El archivo no tiene una configuración válida."
            messagebox.showerror("Radar MQTT", detail)
            return
        if self.listening:
            self.stop_listen()
        self.settings = settings
        save_settings(self.settings)
        self._publish_broker_id = settings.selected_broker_id
        self._refresh_brokers()
        selected = self._broker_by_id(settings.selected_broker_id)
        if selected is not None:
            self._select_broker(selected)
        self._notice("Configuración importada")

    def save_broker(self) -> None:
        try:
            broker = self.read_form()
        except ValueError as error:
            messagebox.showwarning("Radar MQTT", str(error))
            return
        self._store_broker(broker)
        self._notice("Broker guardado")

    def delete_broker(self) -> None:
        broker_id = self._draft_id or self.settings.selected_broker_id
        current = self._broker_by_id(broker_id)
        if current is None:
            self.new_broker()
            return
        if not messagebox.askyesno("Radar MQTT", f"¿Eliminar el broker «{current.name}»?"):
            return
        self.settings.brokers = [broker for broker in self.settings.brokers if broker.id != current.id]
        self.settings.selected_broker_id = self.settings.brokers[0].id if self.settings.brokers else ""
        save_settings(self.settings)
        self._refresh_brokers()
        if self.settings.brokers:
            self._select_broker(self.settings.brokers[0])
        else:
            self.new_broker()

    def toggle_listen(self) -> None:
        if self.listening:
            self.stop_listen()
        else:
            self.start_listen()

    def start_listen(self) -> None:
        try:
            broker = self.read_form()
        except ValueError as error:
            messagebox.showwarning("Radar MQTT", str(error))
            return
        enabled = enabled_topic_names(broker.topics)
        if not enabled:
            self._store_broker(broker)
            messagebox.showwarning("Radar MQTT", "Activá al menos un tópico para escuchar.")
            return
        self._store_broker(broker)
        self._active_topics = enabled
        self._active_qos = broker.qos
        self._user_stop = False
        self.listening = True
        self._message_count = 0
        self.count_label.configure(text="0 mensajes")
        self._set_listening_ui(True)
        self._set_status("Conectando…", WARN)
        self._log(f"Conectando a {broker.host}:{broker.port}", "info")
        threading.Thread(target=self._connect, args=(broker,), daemon=True).start()

    def _connect(self, broker: Broker) -> None:
        try:
            client = self._build_client(broker)
            with self._client_lock:
                if self._user_stop:
                    return
                self.client = client
            client.connect_async(broker.host, broker.port, keepalive=30)
            client.loop_start()
            if self._user_stop:
                self._shutdown_client()
        except Exception as error:
            with self._client_lock:
                self.client = None
            detail = str(error).strip() or error.__class__.__name__
            self.events.put(("failed", detail))

    def _build_client(self, broker: Broker, *, client_id: str | None = None, listen: bool = True) -> mqtt.Client:
        chosen = client_id or broker.client_id.strip() or f"radar-{uuid.uuid4().hex[:8]}"
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=chosen,
            protocol=mqtt.MQTTv311,
            reconnect_on_failure=listen,
        )
        client.reconnect_delay_set(1, 20)
        if broker.username:
            client.username_pw_set(broker.username, broker.password)
        if broker.tls:
            client.tls_set()
        if listen:
            client.on_connect = self._on_connect
            client.on_message = self._on_message
            client.on_disconnect = self._on_disconnect
        return client

    def _on_connect(self, client: mqtt.Client, _userdata: object, _flags: object, reason_code: object, _properties: object) -> None:
        try:
            if getattr(reason_code, "is_failure", reason_code not in (0, "Success")):
                self.events.put(("broker_error", f"El broker rechazó la conexión ({reason_code})"))
                return
            for topic in self._active_topics:
                client.subscribe(topic, qos=self._active_qos)
            self.events.put(("listening", list(self._active_topics)))
        except Exception as error:
            self.events.put(("broker_error", str(error)))

    def _on_message(self, _client: mqtt.Client, _userdata: object, message: mqtt.MQTTMessage) -> None:
        try:
            text = message.payload.decode("utf-8")
        except UnicodeDecodeError:
            text = message.payload.hex()
        self.events.put(("message", message.topic, text))

    def _on_disconnect(self, _client: mqtt.Client, _userdata: object, _flags: object, reason_code: object, _properties: object) -> None:
        if self._user_stop:
            return
        reason = str(reason_code)
        if reason in {"0", "Normal disconnection", "Success"}:
            return
        self.events.put(("reconnecting", reason))

    def stop_listen(self) -> None:
        self._user_stop = True
        self.listening = False
        self._shutdown_client()
        self._set_listening_ui(False)
        self._set_status("Detenido", MUTED)
        self._log("Escucha detenida", "info")

    def _shutdown_client(self) -> None:
        with self._client_lock:
            client = self.client
            self.client = None
        if client is None:
            return
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            return

    def _poll(self) -> None:
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)
        if self.root.winfo_exists():
            self.root.after(150, self._poll)

    def _handle_event(self, event: tuple) -> None:
        kind = event[0]
        if kind == "listening":
            topics = ", ".join(event[1])
            self._set_status("Escuchando", OK)
            self._log(f"Conectado. Escuchando: {topics}", "info")
        elif kind == "message":
            self._show_message(event[1], event[2])
        elif kind == "reconnecting":
            self._set_status("Reconectando…", WARN)
            self._log(f"Se cortó la conexión ({event[1]}). Reintentando…", "error")
        elif kind == "broker_error":
            self._set_status("Reconectando…", WARN)
            self._log(event[1], "error")
        elif kind == "failed":
            self._user_stop = True
            self.listening = False
            self._shutdown_client()
            self._set_listening_ui(False)
            self._set_status("Detenido", ERROR)
            self._log(f"No se pudo conectar: {event[1]}", "error")
        elif kind == "published":
            retained = " retenido" if event[3] else ""
            self._log(f"Publicado{retained} en {event[2]}   ·   {event[1]}", "info")
        elif kind == "publish_failed":
            self._log(f"No se pudo publicar: {event[1]}", "error")
        elif kind == "publish_done":
            self._publishing = False
            self.publish_button.configure(state="normal", text="Publicar")

    def _show_message(self, topic: str, payload: str) -> None:
        matched = match_payload(payload, self.settings.payloads)
        self._message_count += 1
        noun = "mensaje" if self._message_count == 1 else "mensajes"
        self.count_label.configure(text=f"{self._message_count} {noun}")
        visible = payload.replace("\r\n", "\n").replace("\r", "\n")
        stamp = self._now()
        header = f"{stamp}   {topic}"
        if matched:
            header += f"   → {matched.name}"
        formatted = pretty_json(visible)
        shown = formatted if formatted is not None else visible
        self._log_payload(header, shown, formatted is not None, "match" if matched else "msg")

    def _set_listening_ui(self, listening: bool) -> None:
        if listening:
            self.listen_button.configure(text="Detener", bg=ERROR, activebackground="#7E2C26")
        else:
            self.listen_button.configure(text="Comenzar a escuchar", bg=BROWN, activebackground=BROWN_DARK)
        state = "disabled" if listening else "normal"
        combo_state = "disabled" if listening else "readonly"
        self.broker_combo.configure(state=combo_state)
        for entry in self._entries:
            entry.configure(state=state)
        self.port_entry.configure(state=state)
        self.qos_entry.configure(state=state)
        self.tls_check.configure(state=state)
        self.topic_entry.configure(state=state)
        self.add_topic_button.configure(state=state)
        for _frame, _name, _var, check, remove in self._topic_rows:
            check.configure(state=state)
            remove.configure(state=state)
        self.save_broker_button.configure(state=state)
        self.delete_broker_button.configure(state=state)

    def _set_status(self, text: str, color: str) -> None:
        self.status_label.configure(text=text, fg=color)

    def _notice(self, text: str) -> None:
        self.notice_label.configure(text=text)

        def clear_notice() -> None:
            if self.notice_label.winfo_exists():
                self.notice_label.configure(text="")

        self.root.after(2200, clear_notice)

    def _log(self, text: str, tag: str) -> None:
        self._open_log()
        start = self.log.index("end-1c")
        self.log.insert("end", text + "\n")
        self.log.tag_add(tag, start, "end-1c")
        self._close_log()

    def _log_payload(self, header: str, body: str, colored: bool, header_tag: str) -> None:
        self._open_log()
        start = self.log.index("end-1c")
        self.log.insert("end", header + "\n")
        self.log.tag_add(header_tag, start, "end-1c")
        if colored:
            for tag, chunk in json_tokens(body):
                if tag:
                    self.log.insert("end", chunk, tag)
                else:
                    self.log.insert("end", chunk)
        else:
            start = self.log.index("end-1c")
            self.log.insert("end", body)
            self.log.tag_add(header_tag, start, "end-1c")
        self.log.insert("end", " ")
        self._insert_copy_button(body)
        self.log.insert("end", "\n")
        self._close_log()

    def _insert_copy_button(self, text: str) -> None:
        button = tk.Button(
            self.log,
            text="Copiar",
            font=("Segoe UI", 8),
            fg=BROWN,
            bg="white",
            activeforeground=BROWN_DARK,
            activebackground="#EFEAE4",
            relief="flat",
            bd=1,
            padx=6,
            pady=0,
            cursor="hand2",
        )
        button.configure(command=lambda payload=text, widget=button: self._copy_payload(payload, widget))
        self._copy_buttons.append(button)
        self.log.window_create("end", window=button)

    def _copy_payload(self, text: str, button: tk.Button) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        button.configure(text="Listo")

        def restore() -> None:
            if button.winfo_exists():
                button.configure(text="Copiar")

        self.root.after(900, restore)

    def _open_log(self) -> None:
        self.log.configure(state="normal")

    def _close_log(self) -> None:
        line_count = int(self.log.index("end-1c").split(".")[0])
        while line_count > 1000:
            self.log.delete("1.0", "2.0")
            line_count -= 1
        self._prune_copy_buttons()
        self.log.see("end")

    def _guard_log(self, event: tk.Event) -> str | None:
        control = bool(event.state & 0x4)
        key = event.keysym.lower()
        if control and key in {"c", "insert", "a"}:
            return None
        if key in {
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Prior",
            "Next",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
        }:
            return None
        return "break"

    def _copy_log(self) -> None:
        try:
            text = self.log.get("sel.first", "sel.last")
        except tk.TclError:
            text = self.log.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _select_all_log(self, _event: object = None) -> str:
        self.log.tag_add("sel", "1.0", "end-1c")
        self.log.mark_set("insert", "end-1c")
        self.log.see("insert")
        return "break"

    def _show_log_menu(self, event: tk.Event) -> str:
        self._log_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _prune_copy_buttons(self) -> None:
        self._copy_buttons = [button for button in self._copy_buttons if button.winfo_exists()]

    def clear_log(self) -> None:
        self.log.delete("1.0", "end")
        self._prune_copy_buttons()
        self._message_count = 0
        self.count_label.configure(text="0 mensajes")

    def _now(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def on_close(self) -> None:
        self._user_stop = True
        self.listening = False
        self._shutdown_client()
        try:
            broker = self.read_form()
        except ValueError:
            broker = None
        if broker is not None:
            self._store_broker(broker)
        else:
            save_settings(self.settings)
        self.root.destroy()


def main() -> None:
    enable_dpi()
    settings = load_settings()
    app = RadarApp(settings)
    if os.environ.get("RADAR_SELFTEST") == "1":
        app.root.update()
        app.root.destroy()
        return
    app.run()
