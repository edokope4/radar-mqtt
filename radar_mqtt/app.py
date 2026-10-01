from __future__ import annotations

import ctypes
import os
import queue
import threading
import uuid
from datetime import datetime
from tkinter import messagebox, ttk
import tkinter as tk

import paho.mqtt.client as mqtt

from radar_mqtt.storage import (
    Broker,
    SavedPayload,
    Settings,
    load_settings,
    match_payload,
    save_settings,
)

BG = "#F6F3EF"
INK = "#2C211C"
MUTED = "#8A7568"
BROWN = "#6F4E37"
BROWN_DARK = "#5C3A2E"
OK = "#2E7D4F"
WARN = "#C47A3A"
ERROR = "#A33B32"


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
        self._build_payloads(body)
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

        ttk.Label(frame, text="Tópicos, uno por línea").grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 2))
        self.topics_text = tk.Text(frame, height=4, font=("Segoe UI", 10), relief="flat", bg="white", fg=INK)
        self.topics_text.grid(row=8, column=0, columnspan=3, sticky="ew")

        actions = tk.Frame(frame, bg=BG)
        actions.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.save_broker_button = ttk.Button(actions, text="Guardar broker", command=self.save_broker)
        self.save_broker_button.pack(side="left")
        self.delete_broker_button = ttk.Button(actions, text="Eliminar", command=self.delete_broker)
        self.delete_broker_button.pack(side="left", padx=8)
        ttk.Label(actions, text="1883 sin TLS, 8883 con TLS", style="Muted.TLabel").pack(side="right")

    def _build_payloads(self, parent: tk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Payloads guardados", padding=12)
        frame.grid(row=0, column=1, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.payload_list = tk.Listbox(
            frame,
            height=8,
            exportselection=False,
            relief="flat",
            font=("Segoe UI", 10),
            bg="white",
            fg=INK,
            selectbackground=BROWN,
            selectforeground="white",
        )
        self.payload_list.grid(row=0, column=0, sticky="nsew")
        self.payload_list.bind("<<ListboxSelect>>", self._on_payload_selected)

        self.payload_name = tk.StringVar()
        self.payload_body = tk.StringVar()
        ttk.Label(frame, text="Nombre").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.payload_name_entry = ttk.Entry(frame, textvariable=self.payload_name)
        self.payload_name_entry.grid(row=2, column=0, sticky="ew", pady=2)
        ttk.Label(frame, text="Contenido").grid(row=3, column=0, sticky="w")
        self.payload_body_entry = ttk.Entry(frame, textvariable=self.payload_body)
        self.payload_body_entry.grid(row=4, column=0, sticky="ew", pady=2)
        self.payload_body_entry.bind("<Return>", lambda _event: self.add_payload())

        actions = tk.Frame(frame, bg=BG)
        actions.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Agregar", command=self.add_payload).pack(side="left")
        ttk.Button(actions, text="Eliminar", command=self.delete_payload).pack(side="left", padx=8)

        self.only_var = tk.BooleanVar(value=self.settings.only_saved_payloads)
        ttk.Checkbutton(
            frame,
            text="Mostrar solo estos payloads",
            variable=self.only_var,
            command=self._save_filter_flag,
        ).grid(row=6, column=0, sticky="w", pady=(10, 0))
        ttk.Label(
            frame,
            text="Si llega un mensaje igual, se marca con el nombre.",
            style="Muted.TLabel",
            wraplength=280,
        ).grid(row=7, column=0, sticky="w", pady=(6, 0))

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
            wrap="word",
            state="disabled",
            font=("Consolas", 10),
            bg="white",
            fg=INK,
            relief="flat",
            padx=8,
            pady=8,
        )
        self.log.grid(row=1, column=0, sticky="nsew")
        self.log.tag_configure("match", foreground=OK, font=("Consolas", 10, "bold"))
        self.log.tag_configure("info", foreground=BROWN)
        self.log.tag_configure("error", foreground=ERROR)
        self.log.tag_configure("msg", foreground=INK)

    def _load_initial(self) -> None:
        self._refresh_brokers()
        self._refresh_payloads()
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

    def _refresh_payloads(self) -> None:
        self.payload_list.delete(0, "end")
        for item in self.settings.payloads:
            self.payload_list.insert("end", f"{item.name}   ·   {item.body}")

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
        self.topics_text.configure(state="normal")
        self.topics_text.delete("1.0", "end")
        self.topics_text.insert("1.0", "\n".join(broker.topics))
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
        self.topics_text.configure(state="normal")
        self.topics_text.delete("1.0", "end")
        self.topics_text.insert("1.0", "cafetera/hacer")
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
        topics = [line.strip() for line in self.topics_text.get("1.0", "end").splitlines() if line.strip()]
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

    def _on_payload_selected(self, _event: object) -> None:
        index = self._selected_payload_index()
        if index is None:
            return
        item = self.settings.payloads[index]
        self.payload_name.set(item.name)
        self.payload_body.set(item.body)

    def _selected_payload_index(self) -> int | None:
        selection = self.payload_list.curselection()
        if not selection:
            return None
        return int(selection[0])

    def add_payload(self) -> None:
        body = self.payload_body.get().strip()
        if not body:
            messagebox.showwarning("Radar MQTT", "Escribí el contenido del payload.")
            return
        name = self.payload_name.get().strip() or body
        for item in self.settings.payloads:
            if item.body.strip() == body:
                item.name = name
                break
        else:
            self.settings.payloads.append(SavedPayload(id=str(uuid.uuid4()), name=name, body=body))
        save_settings(self.settings)
        self._refresh_payloads()
        self.payload_name.set("")
        self.payload_body.set("")
        self._notice("Payload guardado")

    def delete_payload(self) -> None:
        index = self._selected_payload_index()
        if index is None:
            messagebox.showwarning("Radar MQTT", "Elegí un payload de la lista.")
            return
        item = self.settings.payloads[index]
        if not messagebox.askyesno("Radar MQTT", f"¿Eliminar el payload «{item.name}»?"):
            return
        del self.settings.payloads[index]
        save_settings(self.settings)
        self._refresh_payloads()
        self.payload_name.set("")
        self.payload_body.set("")

    def _save_filter_flag(self) -> None:
        self.settings.only_saved_payloads = bool(self.only_var.get())
        save_settings(self.settings)

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
        self._store_broker(broker)
        self._active_topics = list(broker.topics)
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

    def _build_client(self, broker: Broker) -> mqtt.Client:
        client_id = broker.client_id.strip() or f"radar-{uuid.uuid4().hex[:8]}"
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
            reconnect_on_failure=True,
        )
        client.reconnect_delay_set(1, 20)
        if broker.username:
            client.username_pw_set(broker.username, broker.password)
        if broker.tls:
            client.tls_set()
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

    def _show_message(self, topic: str, payload: str) -> None:
        matched = match_payload(payload, self.settings.payloads)
        if self.only_var.get() and matched is None:
            return
        self._message_count += 1
        noun = "mensaje" if self._message_count == 1 else "mensajes"
        self.count_label.configure(text=f"{self._message_count} {noun}")
        visible = payload.replace("\r", "").replace("\n", "\\n")
        if len(visible) > 500:
            visible = visible[:500] + "…"
        stamp = self._now()
        if matched:
            line = f"{stamp}   {topic}   {visible}   → {matched.name}"
            self._log(line, "match")
        else:
            self._log(f"{stamp}   {topic}   {visible}", "msg")

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
        self.topics_text.configure(state=state)
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
        self.log.configure(state="normal")
        line_count = int(self.log.index("end-1c").split(".")[0])
        if line_count > 1000:
            self.log.delete("1.0", "2.0")
        start = self.log.index("end-1c")
        self.log.insert("end", text + "\n")
        self.log.tag_add(tag, start, "end-1c")
        self.log.configure(state="disabled")
        self.log.see("end")

    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
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
