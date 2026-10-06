"""Cliente gráfico multiplataforma para el juego Tron multijugador."""

from __future__ import annotations

import argparse
import json
import queue
import socket
import threading
import tkinter as tk
from typing import Any

DEFAULT_PORT = 5050
BACKGROUND = "#0a1013"
PANEL = "#111b20"
BOARD = "#071014"
TEXT = "#e8f3f3"
MUTED = "#82969c"
ACCENT = "#25d9f8"
GREEN = "#c3f73a"
RED = "#ff4d6d"
MONO_FONT = "DejaVu Sans Mono"
SANS_FONT = "DejaVu Sans"


class NetworkClient:
    """Lee y escribe mensajes de una conexión TCP sin bloquear la interfaz."""

    def __init__(self, sock: socket.socket, events: queue.Queue) -> None:
        self.sock = sock
        self.events = events
        self.send_lock = threading.Lock()
        self.closed = threading.Event()
        self.reader_thread = threading.Thread(target=self._read_loop, name="tron-network-reader", daemon=True)
        self.reader_thread.start()

    def send(self, message: dict[str, Any]) -> None:
        """Codifica un evento como una línea JSON y lo envía al servidor."""
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False) + "\n"
        with self.send_lock:
            if self.closed.is_set():
                return
            self.sock.sendall(payload.encode("utf-8"))

    def close(self) -> None:
        """Cierra el socket y desbloquea el hilo lector."""
        self.closed.set()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def _read_loop(self) -> None:
        buffer = bytearray()
        try:
            while not self.closed.is_set():
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                while b"\n" in buffer:
                    raw_line, _, remainder = buffer.partition(b"\n")
                    buffer = bytearray(remainder)
                    try:
                        message = json.loads(raw_line.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        self.events.put((self, {"type": "error", "message": "El servidor envió un mensaje inválido"}))
                        continue
                    self.events.put((self, message))
        except OSError:
            pass
        finally:
            self.closed.set()
            self.events.put((self, {"type": "disconnected"}))


class TronClientApp:
    """Construye la interfaz e integra la red con el bucle de Tkinter."""

    def __init__(self, root: tk.Tk, default_host: str, default_name: str, default_port: int) -> None:
        self.root = root
        self.root.title("TRON // Lightcycle Arena")
        self.root.geometry("1240x820")
        self.root.minsize(980, 660)
        self.root.configure(bg=BACKGROUND)

        self.events: queue.Queue = queue.Queue()
        self.network: NetworkClient | None = None
        self.connecting = False
        self.player_id: str | None = None
        self.snapshot: dict[str, Any] | None = None
        self.host_var = tk.StringVar(value=default_host)
        self.port_var = tk.StringVar(value=str(default_port))
        self.name_var = tk.StringVar(value=default_name)
        self.status_var = tk.StringVar(value="SIN CONEXIÓN")
        self.notice_var = tk.StringVar(value="Introduce la dirección del servidor para entrar.")
        self.roster_frame: tk.Frame | None = None
        self.start_button: tk.Button | None = None
        self.connect_button: tk.Button | None = None

        self._build_ui()
        self.root.bind_all("<KeyPress>", self._on_key_press)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._poll_events()
        self._draw_board()

    def _build_ui(self) -> None:
        header = tk.Frame(self.root, bg=BACKGROUND)
        header.pack(fill="x", padx=24, pady=(18, 12))
        brand = tk.Frame(header, bg=BACKGROUND)
        brand.pack(side="left")
        tk.Label(
            brand,
            text="TRON",
            bg=BACKGROUND,
            fg=ACCENT,
            font=(MONO_FONT, 25, "bold"),
        ).pack(side="left")
        tk.Label(
            brand,
            text="  //  LIGHTCYCLE ARENA",
            bg=BACKGROUND,
            fg=MUTED,
            font=(MONO_FONT, 10, "bold"),
        ).pack(side="left", pady=(8, 0))
        tk.Label(
            header,
            textvariable=self.status_var,
            bg=BACKGROUND,
            fg=GREEN,
            font=(MONO_FONT, 10, "bold"),
        ).pack(side="right", pady=(8, 0))
        tk.Frame(self.root, bg="#203139", height=1).pack(fill="x", padx=24)

        body = tk.Frame(self.root, bg=BACKGROUND)
        body.pack(fill="both", expand=True, padx=24, pady=18)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            body,
            bg=BOARD,
            highlightthickness=1,
            highlightbackground="#203139",
            relief="flat",
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", lambda _event: self._draw_board())

        sidebar = tk.Frame(body, bg=BACKGROUND, width=270)
        sidebar.grid(row=0, column=1, sticky="ns", padx=(20, 0))
        sidebar.grid_propagate(False)
        self._build_connection_section(sidebar)
        self._build_roster_section(sidebar)
        self._build_controls_section(sidebar)

        footer = tk.Frame(self.root, bg=BACKGROUND)
        footer.pack(fill="x", padx=24, pady=(0, 12))
        tk.Label(
            footer,
            textvariable=self.notice_var,
            bg=BACKGROUND,
            fg=MUTED,
            font=(SANS_FONT, 9),
            anchor="w",
        ).pack(fill="x")

    def _section_title(self, parent: tk.Widget, title: str) -> None:
        tk.Label(
            parent,
            text=title,
            bg=BACKGROUND,
            fg=ACCENT,
            font=(MONO_FONT, 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 9))

    def _build_connection_section(self, parent: tk.Frame) -> None:
        self._section_title(parent, "CONEXIÓN TCP")
        self._make_entry(parent, "Servidor / IP", self.host_var)
        self._make_entry(parent, "Puerto", self.port_var)
        self._make_entry(parent, "Piloto", self.name_var)
        self.connect_button = tk.Button(
            parent,
            text="CONECTAR",
            command=self._connect,
            bg=ACCENT,
            fg="#071014",
            activebackground="#8beeff",
            activeforeground="#071014",
            relief="flat",
            font=(MONO_FONT, 10, "bold"),
            cursor="hand2",
            pady=9,
        )
        self.connect_button.pack(fill="x", pady=(3, 22))

    def _make_entry(self, parent: tk.Frame, label: str, variable: tk.StringVar) -> None:
        tk.Label(
            parent,
            text=label,
            bg=BACKGROUND,
            fg=MUTED,
            font=(SANS_FONT, 9),
            anchor="w",
        ).pack(fill="x", pady=(4, 3))
        entry = tk.Entry(
            parent,
            textvariable=variable,
            bg=PANEL,
            fg=TEXT,
            insertbackground=ACCENT,
            relief="flat",
            font=(SANS_FONT, 10),
            highlightthickness=1,
            highlightbackground="#293a41",
            highlightcolor=ACCENT,
        )
        entry.pack(fill="x", ipady=7)

    def _build_roster_section(self, parent: tk.Frame) -> None:
        self._section_title(parent, "PILOTOS EN SALA")
        self.roster_frame = tk.Frame(parent, bg=BACKGROUND)
        self.roster_frame.pack(fill="x", pady=(0, 21))
        self._render_roster()

    def _build_controls_section(self, parent: tk.Frame) -> None:
        self._section_title(parent, "CARRERA")
        self.start_button = tk.Button(
            parent,
            text="INICIAR CARRERA",
            command=self._send_race_action,
            bg="#18282e",
            fg=MUTED,
            activebackground="#20383f",
            activeforeground=TEXT,
            disabledforeground="#53656b",
            relief="flat",
            font=(MONO_FONT, 9, "bold"),
            cursor="hand2",
            pady=10,
            state="disabled",
        )
        self.start_button.pack(fill="x", pady=(0, 17))
        tk.Label(
            parent,
            text="FLECHAS  /  WASD\nGira para esquivar estelas.\nEl borde también elimina.",
            bg=BACKGROUND,
            fg=MUTED,
            justify="left",
            anchor="w",
            font=(SANS_FONT, 9),
        ).pack(fill="x")

    def _connect(self) -> None:
        if self.network is not None or self.connecting:
            return
        host = self.host_var.get().strip()
        name = self.name_var.get().strip()[:16] or "Jugador"
        try:
            port = int(self.port_var.get())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.notice_var.set("El puerto debe ser un número entre 1 y 65535.")
            return
        if not host:
            self.notice_var.set("Escribe la dirección IP o el nombre del servidor.")
            return

        self.name_var.set(name)
        self.connecting = True
        self.notice_var.set(f"Conectando con {host}:{port}...")
        self._refresh_controls()
        threading.Thread(
            target=self._connect_worker,
            args=(host, port, name),
            name="tron-connect",
            daemon=True,
        ).start()

    def _connect_worker(self, host: str, port: int, name: str) -> None:
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.settimeout(None)
            network = NetworkClient(sock, self.events)
            self.network = network
            network.send({"type": "join", "name": name})
            self.events.put((network, {"type": "connected"}))
        except (OSError, ValueError) as exc:
            self.events.put((None, {"type": "connect_error", "message": str(exc)}))

    def _poll_events(self) -> None:
        while True:
            try:
                network, message = self.events.get_nowait()
            except queue.Empty:
                break
            if message.get("type") == "connect_error":
                self.connecting = False
                self.notice_var.set(f"No se pudo conectar: {message['message']}")
                self._refresh_controls()
                continue
            if network is not self.network:
                continue
            message_type = message.get("type")
            if message_type == "connected":
                self.connecting = False
                self.notice_var.set("Conectado. Espera a que haya tres pilotos para iniciar.")
            elif message_type == "welcome":
                self.player_id = message.get("player_id")
                self.snapshot = message.get("snapshot")
                self._update_game_view()
            elif message_type == "state":
                self.snapshot = message.get("snapshot")
                self._update_game_view()
            elif message_type == "error":
                self.notice_var.set(message.get("message", "Error del servidor"))
            elif message_type == "disconnected":
                self.network = None
                self.connecting = False
                self.player_id = None
                self.snapshot = None
                self.status_var.set("SIN CONEXIÓN")
                self.notice_var.set("Se perdió la conexión con el servidor.")
                self._render_roster()
                self._draw_board()
            self._refresh_controls()
        self.root.after(40, self._poll_events)

    def _update_game_view(self) -> None:
        self._render_roster()
        self._draw_board()
        self._refresh_controls()

    def _render_roster(self) -> None:
        if self.roster_frame is None:
            return
        for child in self.roster_frame.winfo_children():
            child.destroy()
        players = self.snapshot.get("players", []) if self.snapshot else []
        if not players:
            tk.Label(
                self.roster_frame,
                text="Sin pilotos conectados",
                bg=BACKGROUND,
                fg=MUTED,
                font=(SANS_FONT, 9),
                anchor="w",
            ).pack(fill="x", pady=3)
        for player in players:
            row = tk.Frame(self.roster_frame, bg=BACKGROUND)
            row.pack(fill="x", pady=3)
            tk.Label(
                row,
                text="●",
                bg=BACKGROUND,
                fg=player["color"] if player["alive"] else "#536168",
                font=(SANS_FONT, 11),
            ).pack(side="left")
            suffix = "  (tú)" if player["id"] == self.player_id else ""
            tk.Label(
                row,
                text=f"  {player['name']}{suffix}",
                bg=BACKGROUND,
                fg=TEXT if player["alive"] else MUTED,
                font=(SANS_FONT, 9),
                anchor="w",
            ).pack(side="left")
            if not player["alive"]:
                tk.Label(row, text="FUERA", bg=BACKGROUND, fg=RED, font=(MONO_FONT, 7)).pack(side="right")

    def _refresh_controls(self) -> None:
        if self.connect_button is not None:
            self.connect_button.configure(
                state="disabled" if self.network is not None or self.connecting else "normal",
                text="CONECTANDO..." if self.connecting else "CONECTADO" if self.network else "CONECTAR",
            )
        if self.network is None:
            self.status_var.set("CONECTANDO" if self.connecting else "SIN CONEXIÓN")
        elif self.snapshot is None:
            self.status_var.set("CONECTADO")
        else:
            phase = self.snapshot["phase"]
            count = len(self.snapshot.get("players", []))
            if phase == "lobby":
                self.status_var.set(f"SALA ABIERTA  /  {count} JUGADORES")
            elif phase == "running":
                self.status_var.set("CARRERA EN CURSO")
            else:
                self.status_var.set("CARRERA FINALIZADA")

        if self.start_button is None:
            return
        phase = self.snapshot.get("phase") if self.snapshot else None
        count = len(self.snapshot.get("players", [])) if self.snapshot else 0
        if self.network is None:
            self.start_button.configure(text="INICIAR CARRERA", state="disabled")
        elif phase == "lobby":
            enabled = count >= 3
            self.start_button.configure(text="INICIAR CARRERA", state="normal" if enabled else "disabled")
        elif phase == "finished":
            self.start_button.configure(text="JUGAR OTRA VEZ", state="normal")
        else:
            self.start_button.configure(text="CARRERA EN CURSO", state="disabled")

    def _send_race_action(self) -> None:
        if self.network is None or self.snapshot is None:
            return
        action = "start" if self.snapshot["phase"] == "lobby" else "restart"
        try:
            self.network.send({"type": action})
        except OSError:
            self.notice_var.set("No se pudo enviar la acción al servidor.")

    def _on_key_press(self, event: tk.Event) -> None:
        if isinstance(self.root.focus_get(), tk.Entry):
            return
        direction_by_key = {
            "Up": "up",
            "w": "up",
            "W": "up",
            "Down": "down",
            "s": "down",
            "S": "down",
            "Left": "left",
            "a": "left",
            "A": "left",
            "Right": "right",
            "d": "right",
            "D": "right",
        }
        direction = direction_by_key.get(event.keysym)
        if direction is None or self.network is None or not self.snapshot:
            return
        if self.snapshot["phase"] != "running":
            return
        try:
            self.network.send({"type": "direction", "direction": direction})
        except OSError:
            self.notice_var.set("No se pudo enviar el movimiento.")

    def _draw_board(self) -> None:
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        board_width = self.snapshot.get("width", 48) if self.snapshot else 48
        board_height = self.snapshot.get("height", 32) if self.snapshot else 32
        cell = min(width / board_width, height / board_height)
        left = (width - cell * board_width) / 2
        top = (height - cell * board_height) / 2

        for column in range(board_width + 1):
            x = left + column * cell
            canvas.create_line(x, top, x, top + board_height * cell, fill="#122127", width=1)
        for row in range(board_height + 1):
            y = top + row * cell
            canvas.create_line(left, y, left + board_width * cell, y, fill="#122127", width=1)

        if self.snapshot:
            for player in self.snapshot.get("players", []):
                trail = player.get("trail", [])
                if len(trail) > 1:
                    coordinates = []
                    for x, y in trail:
                        coordinates.extend((left + (x + 0.5) * cell, top + (y + 0.5) * cell))
                    canvas.create_line(
                        *coordinates,
                        fill=player["color"],
                        width=max(3, cell * 0.66),
                        capstyle=tk.ROUND,
                        joinstyle=tk.ROUND,
                    )
                head_x = left + (player["x"] + 0.5) * cell
                head_y = top + (player["y"] + 0.5) * cell
                radius = max(3, cell * 0.33)
                canvas.create_oval(
                    head_x - radius,
                    head_y - radius,
                    head_x + radius,
                    head_y + radius,
                    fill=player["color"] if player["alive"] else "#536168",
                    outline=TEXT if player["alive"] else "#536168",
                    width=1,
                )

        phase = self.snapshot.get("phase") if self.snapshot else "lobby"
        if phase == "lobby":
            count = len(self.snapshot.get("players", [])) if self.snapshot else 0
            message = "ESPERANDO PILOTOS" if count < 3 else "SALA LISTA"
            detail = f"{count} / 3 PILOTOS MÍNIMO"
            self._draw_overlay(left, top, board_width * cell, board_height * cell, message, detail)
        elif phase == "finished":
            winner_id = self.snapshot.get("winner")
            winner = next(
                (player["name"] for player in self.snapshot.get("players", []) if player["id"] == winner_id),
                None,
            )
            message = f"{winner} GANA" if winner else "SIN SUPERVIVIENTES"
            self._draw_overlay(left, top, board_width * cell, board_height * cell, message, "PULSA JUGAR OTRA VEZ")

    def _draw_overlay(self, x: float, y: float, width: float, height: float, title: str, detail: str) -> None:
        center_x = x + width / 2
        center_y = y + height / 2
        self.canvas.create_rectangle(
            center_x - 205,
            center_y - 48,
            center_x + 205,
            center_y + 48,
            fill="#0a1419",
            outline="#29404a",
        )
        self.canvas.create_text(
            center_x,
            center_y - 14,
            text=title,
            fill=ACCENT,
            font=(MONO_FONT, 16, "bold"),
        )
        self.canvas.create_text(
            center_x,
            center_y + 18,
            text=detail,
            fill=MUTED,
            font=(MONO_FONT, 9),
        )

    def _on_close(self) -> None:
        if self.network is not None:
            self.network.close()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente gráfico para Tron multijugador")
    parser.add_argument("--host", default="127.0.0.1", help="Dirección del servidor")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Puerto TCP del servidor")
    parser.add_argument("--name", default="Jugador", help="Nombre inicial del piloto")
    args = parser.parse_args()

    root = tk.Tk()
    TronClientApp(root, args.host, args.name, args.port)
    root.mainloop()


if __name__ == "__main__":
    main()
