import asyncio
import websockets
import json

class Network:
    def __init__(self):
        self.uri = "ws://localhost:8766"  # Ensure this matches the server's port
        self.websocket = None
        self.player = None
        self.game_id = None

    async def connect(self):
        try:
            self.websocket = await websockets.connect(self.uri)
            print("Connected to server")
            
            try:
                response = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
                data = json.loads(response)
                
                if data["type"] == "waiting":
                    print("Waiting for another player...")
                    response = await self.websocket.recv()
                    data = json.loads(response)
                
                if data["type"] == "game_start":
                    self.player = data["player"]
                    self.game_id = data["game_id"]
                    print(f"Game started! You are player {self.player}. Game ID: {self.game_id}")
            
            except asyncio.TimeoutError:
                print("Timeout: No response from server.")
            
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed: {e}")
        except Exception as e:
            print(f"Failed to connect: {e}")

    async def setup_characters(self, characters):
        await self.send_message({
            "type": "setup",
            "characters": characters
        })

    async def make_move(self, position, direction):
        await self.send_message({
            "type": "move",
            "position": position,
            "direction": direction
        })

    async def send_message(self, message):
        try:
            await self.websocket.send(json.dumps(message))
            print(f"Sent message: {message}")
            response = await self.websocket.recv()
            print(f"Received response: {response}")
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed while sending message: {e}")
        except Exception as e:
            print(f"Error sending message: {e}")

    async def receive_game_state(self):
        try:
            response = await self.websocket.recv()
            data = json.loads(response)
            if data['type'] == 'state':
                print(f"Game state: {data['state']}")
            elif data['type'] == 'error':
                print(f"Error from server: {data['message']}")
        except websockets.exceptions.ConnectionClosedError as e:
            print(f"Connection closed while receiving game state: {e}")
        except Exception as e:
            print(f"Error receiving game state: {e}")

    async def close_connection(self):
        try:
            if self.websocket:
                await self.websocket.close()
                print("Connection closed")
        except Exception as e:
            print(f"Error closing connection: {e}")

async def main():
    network = Network()
    await network.connect()

    characters = ["PAWN", "HERO1", "HERO2", "HERO3"]
    await network.setup_characters(characters)

    position = (0, 0)
    direction = "R"
    await network.make_move(position, direction)

    await network.receive_game_state()

    await network.close_connection()

if __name__ == "__main__":
    asyncio.run(main())
