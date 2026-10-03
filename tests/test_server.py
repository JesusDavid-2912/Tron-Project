import json
import socket
import unittest

from server import GameServer


class ServerIntegrationTests(unittest.TestCase):
    def test_three_tcp_clients_start_a_shared_round(self) -> None:
        server = GameServer(host="127.0.0.1", port=0, tick_rate=15)
        server.start()
        clients: list[socket.socket] = []
        streams = []
        try:
            invalid_client = socket.create_connection(("127.0.0.1", server.port), timeout=2)
            invalid_client.settimeout(2)
            invalid_stream = invalid_client.makefile("r", encoding="utf-8")
            invalid_client.sendall(b'[]\n')
            rejection = json.loads(invalid_stream.readline())
            self.assertEqual(rejection["type"], "error")
            invalid_stream.close()
            invalid_client.close()

            for name in ("Ada", "Linus", "Grace"):
                client = socket.create_connection(("127.0.0.1", server.port), timeout=2)
                client.settimeout(2)
                clients.append(client)
                stream = client.makefile("r", encoding="utf-8")
                streams.append(stream)
                client.sendall((json.dumps({"type": "join", "name": name}) + "\n").encode())
                welcome = json.loads(stream.readline())
                self.assertEqual(welcome["type"], "welcome")

            clients[0].sendall(b'{"type":"start"}\n')
            received_running_state = False
            for line in streams[0]:
                message = json.loads(line)
                if message.get("type") == "state" and message["snapshot"]["phase"] == "running":
                    received_running_state = True
                    self.assertEqual(len(message["snapshot"]["players"]), 3)
                    break
            self.assertTrue(received_running_state)
        finally:
            for stream in streams:
                stream.close()
            for client in clients:
                client.close()
            server.stop()


if __name__ == "__main__":
    unittest.main()