import unittest

from game import GameState


class GameStateTests(unittest.TestCase):
    def make_game(self) -> GameState:
        game = GameState()
        for player_id in ("one", "two", "three"):
            game.add_player(player_id, player_id)
        return game

    def test_requires_three_players_to_start(self) -> None:
        game = GameState()
        game.add_player("one", "One")
        with self.assertRaisesRegex(ValueError, "al menos 3"):
            game.start()

    def test_players_move_simultaneously_and_keep_trails(self) -> None:
        game = self.make_game()
        game.start()
        positions = {player.player_id: (player.x, player.y) for player in game.players.values()}

        game.tick()

        for player in game.players.values():
            self.assertNotEqual((player.x, player.y), positions[player.player_id])
            self.assertEqual(len(player.trail), 2)
        self.assertEqual(game.phase, "running")

    def test_opposite_turn_is_rejected(self) -> None:
        game = self.make_game()
        game.start()

        self.assertFalse(game.set_direction("one", "left"))
        self.assertTrue(game.set_direction("one", "up"))

    def test_replacement_player_uses_an_unoccupied_spawn(self) -> None:
        game = GameState()
        first = game.add_player("one", "One")
        second = game.add_player("two", "Two")
        game.remove_player(first.player_id)

        replacement = game.add_player("three", "Three")

        self.assertNotEqual((replacement.x, replacement.y), (second.x, second.y))

    def test_duplicate_destination_kills_both_riders(self) -> None:
        game = self.make_game()
        game.start()
        first = game.players["one"]
        second = game.players["two"]
        third = game.players["three"]
        first.x, first.y, first.direction = 10, 10, "right"
        second.x, second.y, second.direction = 12, 10, "left"
        third.x, third.y, third.direction = 24, 5, "down"
        first.trail = [(10, 10)]
        second.trail = [(12, 10)]
        third.trail = [(24, 5)]

        game.tick()

        self.assertFalse(first.alive)
        self.assertFalse(second.alive)
        self.assertTrue(third.alive)
        self.assertEqual(game.phase, "finished")
        self.assertEqual(game.winner, "three")


if __name__ == "__main__":
    unittest.main()