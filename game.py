"""Modelo autoritativo de una partida de Tron en una cuadrícula."""

from __future__ import annotations

from dataclasses import dataclass, field

BOARD_WIDTH = 48
BOARD_HEIGHT = 32
MAX_PLAYERS = 6
SPAWN_POINTS = (
    (6, 16, "right"),
    (41, 16, "left"),
    (24, 5, "down"),
    (24, 26, "up"),
    (12, 8, "right"),
    (35, 23, "left"),
)
PLAYER_COLORS = ("#25d9f8", "#ff4d6d", "#c3f73a", "#ffb627", "#ae7bff", "#f58bd6")
DIRECTIONS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
OPPOSITE = {"up": "down", "down": "up", "left": "right", "right": "left"}


@dataclass
class Player:
    """Estado persistente de un jugador durante una ronda."""

    player_id: str
    name: str
    color: str
    x: int
    y: int
    direction: str
    alive: bool = True
    trail: list[tuple[int, int]] = field(default_factory=list)
    pending_direction: str | None = None


class GameState:
    """Mantiene los jugadores y aplica las reglas de la partida."""

    def __init__(self) -> None:
        self.players: dict[str, Player] = {}
        self.phase = "lobby"
        self.winner: str | None = None
        self.tick_number = 0

    def add_player(self, player_id: str, name: str) -> Player:
        """Registra un jugador y le asigna un punto de aparición."""
        if self.phase != "lobby":
            raise ValueError("La partida ya comenzó")
        if len(self.players) >= MAX_PLAYERS:
            raise ValueError("La sala está llena")
        if player_id in self.players:
            raise ValueError("El identificador ya está en uso")
        occupied_spawns = {(player.x, player.y) for player in self.players.values()}
        slot = next(
            index
            for index, (x, y, _direction) in enumerate(SPAWN_POINTS)
            if (x, y) not in occupied_spawns
        )
        x, y, direction = SPAWN_POINTS[slot]
        player = Player(
            player_id=player_id,
            name=name,
            color=PLAYER_COLORS[slot],
            x=x,
            y=y,
            direction=direction,
            trail=[(x, y)],
        )
        self.players[player_id] = player
        return player

    def remove_player(self, player_id: str) -> None:
        """Elimina a un jugador desconectado de la sala."""
        self.players.pop(player_id, None)

    def start(self) -> None:
        """Inicia la ronda cuando hay al menos tres participantes."""
        if self.phase != "lobby":
            raise ValueError("La sala no está esperando jugadores")
        if len(self.players) < 3:
            raise ValueError("Se necesitan al menos 3 jugadores")
        self.phase = "running"

    def set_direction(self, player_id: str, direction: str) -> bool:
        """Guarda un giro válido para el siguiente paso de movimiento."""
        player = self.players.get(player_id)
        if self.phase != "running" or player is None or not player.alive:
            return False
        if direction not in DIRECTIONS:
            return False
        current = player.pending_direction or player.direction
        if direction == OPPOSITE[current]:
            return False
        player.pending_direction = direction
        return True

    def tick(self) -> None:
        """Avanza una celda y resuelve todas las colisiones del mismo paso."""
        if self.phase != "running":
            return

        alive_players = [player for player in self.players.values() if player.alive]
        occupied = {cell for player in self.players.values() for cell in player.trail}
        destinations: dict[str, tuple[int, int]] = {}
        for player in alive_players:
            if player.pending_direction is not None:
                player.direction = player.pending_direction
                player.pending_direction = None
            dx, dy = DIRECTIONS[player.direction]
            destinations[player.player_id] = (player.x + dx, player.y + dy)

        collisions: set[str] = set()
        for player_id, (x, y) in destinations.items():
            if not (0 <= x < BOARD_WIDTH and 0 <= y < BOARD_HEIGHT):
                collisions.add(player_id)
            elif (x, y) in occupied:
                collisions.add(player_id)

        destination_counts: dict[tuple[int, int], int] = {}
        for destination in destinations.values():
            destination_counts[destination] = destination_counts.get(destination, 0) + 1
        collisions.update(
            player_id
            for player_id, destination in destinations.items()
            if destination_counts[destination] > 1
        )

        for player in alive_players:
            if player.player_id in collisions:
                player.alive = False
            else:
                player.x, player.y = destinations[player.player_id]
                player.trail.append((player.x, player.y))

        self.tick_number += 1
        survivors = [player for player in self.players.values() if player.alive]
        if len(survivors) <= 1:
            self.phase = "finished"
            self.winner = survivors[0].player_id if survivors else None

    def restart(self) -> None:
        """Devuelve la sala a espera y prepara otra ronda con los mismos jugadores."""
        self.phase = "lobby"
        self.winner = None
        self.tick_number = 0
        for slot, player in enumerate(self.players.values()):
            x, y, direction = SPAWN_POINTS[slot]
            player.x = x
            player.y = y
            player.direction = direction
            player.pending_direction = None
            player.alive = True
            player.trail = [(x, y)]

    def snapshot(self) -> dict:
        """Crea una instantánea serializable para distribuir a los clientes."""
        return {
            "phase": self.phase,
            "winner": self.winner,
            "tick": self.tick_number,
            "width": BOARD_WIDTH,
            "height": BOARD_HEIGHT,
            "players": [
                {
                    "id": player.player_id,
                    "name": player.name,
                    "color": player.color,
                    "x": player.x,
                    "y": player.y,
                    "alive": player.alive,
                    "trail": player.trail,
                }
                for player in self.players.values()
            ],
        }