"""Servidor TCP concurrente y autoritativo para Tron."""

from __future__ import annotations

import argparse
import json
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from game import GameState, MAX_PLAYERS


@dataclass
class ClientConnection:
    """Conexión TCP con escritura sincronizada para cada cliente."""

    sock: socket.socket
    player_id: str
    name: str
    send_lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, message: dict[str, Any]) -> None:
        """Envía un mensaje JSON en una línea, protegido contra escrituras simultáneas."""
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=True) + "\n"
        with self.send_lock:
            self.sock.sendall(payload.encode("utf-8"))


class GameServer:
    """Coordina las conexiones TCP y mantiene el estado autoritativo.

    Un bloqueo protege el modelo compartido. El hilo de aceptación crea un
    hilo por cliente y el hilo de simulación avanza la partida y difunde estados.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 5050, tick_rate: int = 10) -> None:
        """Configura el servidor sin abrir todavía el puerto.

        Args:
            host: Interfaz de red donde se aceptan conexiones.
            port: Puerto TCP, entre 0 y 65535; cero solicita uno disponible.
            tick_rate: Pasos de simulación por segundo, entre 1 y 30.

        Raises:
            ValueError: Si la frecuencia está fuera del intervalo permitido.
        """
        if tick_rate < 1 or tick_rate > 30:
            raise ValueError("La frecuencia debe estar entre 1 y 30 pasos por segundo")
        self.host = host
        self.port = port
        self.tick_rate = tick_rate
        self.game = GameState()
        self.lock = threading.RLock()
        self.clients: dict[str, ClientConnection] = {}
        self.stop_event = threading.Event()
        self.listener: socket.socket | None = None
        self.accept_thread: threading.Thread | None = None
        self.tick_thread: threading.Thread | None = None

    def start(self) -> None:
        """Abre el socket de escucha e inicia aceptación y simulación.

        El puerto efectivo queda disponible en `self.port`, incluso cuando se
        configuró cero para pedir uno dinámico.

        Raises:
            RuntimeError: Si el servidor ya fue iniciado.
            OSError: Si no se puede enlazar o abrir el puerto solicitado.
        """
        if self.listener is not None:
            raise RuntimeError("El servidor ya está iniciado")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.host, self.port))
        listener.listen(MAX_PLAYERS)
        listener.settimeout(0.5)
        self.listener = listener
        self.port = listener.getsockname()[1]
        self.stop_event.clear()
        self.accept_thread = threading.Thread(target=self._accept_loop, name="tron-accept", daemon=True)
        self.tick_thread = threading.Thread(target=self._tick_loop, name="tron-tick", daemon=True)
        self.accept_thread.start()
        self.tick_thread.start()
        print(f"Servidor Tron escuchando en {self.host}:{self.port} (TCP)", flush=True)

    def serve_forever(self) -> None:
        """Ejecuta el servidor hasta una interrupción y luego lo cierra."""
        self.start()
        try:
            self.stop_event.wait()
        except KeyboardInterrupt:
            print("\nCerrando servidor...", flush=True)
        finally:
            self.stop()

    def stop(self) -> None:
        """Cierra el socket de escucha y las conexiones activas.

        La operación puede llamarse al finalizar el proceso o desde una prueba;
        los hilos de servicio son demonios y se espera brevemente su salida.
        """
        self.stop_event.set()
        if self.listener is not None:
            self.listener.close()
            self.listener = None
        with self.lock:
            connections = list(self.clients.values())
        for connection in connections:
            self._close_socket(connection.sock)
        for thread in (self.accept_thread, self.tick_thread):
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=1)

    def _accept_loop(self) -> None:
        """Acepta conexiones y delega cada cliente a un hilo independiente."""
        while not self.stop_event.is_set():
            listener = self.listener
            if listener is None:
                return
            try:
                client_socket, address = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            thread = threading.Thread(
                target=self._handle_client,
                args=(client_socket, address),
                name=f"tron-client-{address[0]}",
                daemon=True,
            )
            thread.start()

    def _handle_client(self, client_socket: socket.socket, address: tuple[str, int]) -> None:
        """Valida el saludo, registra al piloto y procesa sus eventos.

        El primer mensaje debe ser un objeto JSON `join`. Al terminar la
        conexión, un piloto en sala se elimina; durante una ronda se marca
        como eliminado para conservar su estela.
        """
        connection: ClientConnection | None = None
        reader = None
        try:
            reader = client_socket.makefile("r", encoding="utf-8", newline="\n")
            first_line = reader.readline()
            if not first_line:
                return
            try:
                request = json.loads(first_line)
            except json.JSONDecodeError:
                self._send_raw_error(client_socket, "El primer mensaje debe ser JSON válido")
                return
            if not isinstance(request, dict):
                self._send_raw_error(client_socket, "El primer mensaje debe ser un objeto JSON")
                return
            if request.get("type") != "join":
                self._send_raw_error(client_socket, "Envía un mensaje join para entrar a la sala")
                return
            name = str(request.get("name", "Jugador")).strip()[:16] or "Jugador"
            player_id = uuid.uuid4().hex[:8]
            with self.lock:
                if self.game.phase != "lobby":
                    self._send_raw_error(client_socket, "La partida ya comenzó")
                    return
                if len(self.clients) >= MAX_PLAYERS:
                    self._send_raw_error(client_socket, "La sala admite hasta 6 jugadores")
                    return
                self.game.add_player(player_id, name)
                connection = ClientConnection(client_socket, player_id, name)
                self.clients[player_id] = connection
                snapshot = self.game.snapshot()
                connection.send({"type": "welcome", "player_id": player_id, "snapshot": snapshot})
            print(f"{name} se conectó desde {address[0]}", flush=True)

            for line in reader:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    connection.send({"type": "error", "message": "Mensaje JSON inválido"})
                    continue
                if not isinstance(message, dict):
                    connection.send({"type": "error", "message": "Cada evento debe ser un objeto JSON"})
                    continue
                self._handle_message(connection, message)
        except (ConnectionError, OSError, UnicodeDecodeError):
            pass
        finally:
            if reader is not None:
                reader.close()
            self._close_socket(client_socket)
            if connection is not None:
                with self.lock:
                    self.clients.pop(connection.player_id, None)
                    player = self.game.players.get(connection.player_id)
                    if player is not None:
                        if self.game.phase == "running":
                            player.alive = False
                        else:
                            self.game.remove_player(connection.player_id)
                print(f"{connection.name} se desconectó", flush=True)

    def _handle_message(self, connection: ClientConnection, message: dict[str, Any]) -> None:
        """Valida y aplica `direction`, `start` o `restart` bajo el bloqueo."""
        command = message.get("type")
        error: str | None = None
        with self.lock:
            if command == "direction":
                if not self.game.set_direction(connection.player_id, str(message.get("direction", ""))):
                    return
            elif command == "start":
                try:
                    self.game.start()
                except ValueError as exc:
                    error = str(exc)
            elif command == "restart":
                if self.game.phase != "finished":
                    error = "La ronda actual todavía no termina"
                else:
                    connected_ids = set(self.clients)
                    for player_id in list(self.game.players):
                        if player_id not in connected_ids:
                            self.game.remove_player(player_id)
                    self.game.restart()
            else:
                error = "Tipo de evento desconocido"
        if error is not None:
            try:
                connection.send({"type": "error", "message": error})
            except OSError:
                self._close_socket(connection.sock)

    def _tick_loop(self) -> None:
        """Avanza la simulación y transmite una instantánea a cada cliente.

        La frecuencia se controla con `tick_rate`; también se envían estados
        durante la sala de espera para actualizar la lista de pilotos.
        """
        interval = 1 / self.tick_rate
        deadline = time.monotonic()
        while not self.stop_event.is_set():
            with self.lock:
                if self.game.phase == "running":
                    self.game.tick()
                snapshot = self.game.snapshot()
                connections = list(self.clients.values())
            for connection in connections:
                try:
                    connection.send({"type": "state", "snapshot": snapshot})
                except OSError:
                    self._close_socket(connection.sock)
            deadline += interval
            self.stop_event.wait(max(0.0, deadline - time.monotonic()))

    @staticmethod
    def _send_raw_error(client_socket: socket.socket, message: str) -> None:
        """Responde con un error JSON antes de registrar una conexión."""
        payload = json.dumps({"type": "error", "message": message}) + "\n"
        try:
            client_socket.sendall(payload.encode("utf-8"))
        except OSError:
            pass

    @staticmethod
    def _close_socket(client_socket: socket.socket) -> None:
        """Apaga y cierra un socket; tolera que ya esté desconectado."""
        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            client_socket.close()
        except OSError:
            pass


def main() -> None:
    """Lee las opciones de línea de comandos y ejecuta el servidor."""
    parser = argparse.ArgumentParser(description="Servidor TCP para Tron multijugador")
    parser.add_argument("--host", default="0.0.0.0", help="Interfaz de red (por defecto: todas)")
    parser.add_argument("--port", type=int, default=5050, help="Puerto TCP (por defecto: 5050)")
    parser.add_argument("--tick-rate", type=int, default=10, help="Pasos de juego por segundo (1-30)")
    args = parser.parse_args()
    GameServer(args.host, args.port, args.tick_rate).serve_forever()


if __name__ == "__main__":
    main()
