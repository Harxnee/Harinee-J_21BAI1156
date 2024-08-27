import asyncio
import websockets
import json
import random

class Character:
    def __init__(self, char_type, player, position):
        self.type = char_type
        self.player = player
        self.position = position

class GameState:
    def __init__(self):
        self.board = [[None for _ in range(5)] for _ in range(5)]
        self.players = []
        self.current_player = 0
        self.game_over = False
        self.winner = None

    def setup_characters(self, player, characters):
        row = 0 if player == 0 else 4
        for col, char_type in enumerate(characters):
            self.board[row][col] = Character(char_type, player, (row, col))
        print(f"Player {player} setup characters: {characters}")

    def is_valid_move(self, player, char_pos, direction):
        if player != self.current_player:
            print(f"Invalid move: Not player {player}'s turn")
            return False

        char = self.board[char_pos[0]][char_pos[1]]
        if char is None or char.player != player:
            print(f"Invalid move: No character of player {player} at position {char_pos}")
            return False

        new_pos = self.calculate_new_position(char, direction)
        if new_pos is None:
            print(f"Invalid move: Direction {direction} leads to an invalid position")
            return False

        return True

    def calculate_new_position(self, char, direction):
        row, col = char.position
        moves = {
            "PAWN": {"L": (0, -1), "R": (0, 1), "F": (-1, 0), "B": (1, 0)},
            "HERO1": {"L": (0, -2), "R": (0, 2), "F": (-2, 0), "B": (2, 0)},
            "HERO2": {"FL": (-2, -2), "FR": (-2, 2), "BL": (2, -2), "BR": (2, 2)},
            "HERO3": {
                "FL": (-2, -1), "FR": (-2, 1), "BL": (2, -1), "BR": (2, 1),
                "RF": (-1, 2), "RB": (1, 2), "LF": (-1, -2), "LB": (1, -2)
            }
        }
        dr, dc = moves[char.type].get(direction, (0, 0))
        new_row, new_col = row + dr, col + dc

        if 0 <= new_row < 5 and 0 <= new_col < 5:
            return (new_row, new_col)
        return None

    def make_move(self, char_pos, direction):
        char = self.board[char_pos[0]][char_pos[1]]
        new_pos = self.calculate_new_position(char, direction)

        # Move the character
        self.board[char_pos[0]][char_pos[1]] = None
        self.board[new_pos[0]][new_pos[1]] = char
        char.position = new_pos
        print(f"Player {char.player} moved {char.type} from {char_pos} to {new_pos}")

        # Check for capture
        self.check_capture(char, new_pos)

        # Switch turns
        self.current_player = 1 - self.current_player

        # Check for game over
        self.check_game_over()

    def check_capture(self, char, new_pos):
        if char.type in ["HERO1", "HERO2"]:
            # Capture all enemies in the path
            start_row, start_col = char.position
            end_row, end_col = new_pos
            step_row = 1 if end_row > start_row else -1 if end_row < start_row else 0
            step_col = 1 if end_col > start_col else -1 if end_col < start_col else 0

            row, col = start_row + step_row, start_col + step_col
            while (row, col) != new_pos:
                if self.board[row][col] and self.board[row][col].player != char.player:
                    print(f"Player {char.player} captured opponent's character at {(row, col)}")
                    self.board[row][col] = None
                row += step_row
                col += step_col
        
        # Capture enemy at the final position for all character types
        if self.board[new_pos[0]][new_pos[1]] and self.board[new_pos[0]][new_pos[1]].player != char.player:
            print(f"Player {char.player} captured opponent's character at {new_pos}")
            self.board[new_pos[0]][new_pos[1]] = None

    def check_game_over(self):
        players_alive = set()
        for row in self.board:
            for char in row:
                if char:
                    players_alive.add(char.player)
        
        if len(players_alive) < 2:
            self.game_over = True
            self.winner = players_alive.pop() if players_alive else None
            print(f"Game over! Winner: Player {self.winner}")

    def get_state(self):
        return {
            "board": [
                [
                    {"type": cell.type, "player": cell.player} if cell else None
                    for cell in row
                ]
                for row in self.board
            ],
            "current_player": self.current_player,
            "game_over": self.game_over,
            "winner": self.winner
        }

class GameServer:
    def __init__(self):
        self.games = {}
        self.waiting_player = None

    async def handle_connection(self, websocket, path):
        game_id = None
        try:
            if self.waiting_player:
                game_id = str(random.randint(1000, 9999))
                self.games[game_id] = GameState()
                self.games[game_id].players = [self.waiting_player, websocket]
                if self.waiting_player.open:
                    await self.waiting_player.send(json.dumps({"type": "game_start", "player": 0, "game_id": game_id}))
                if websocket.open:
                    await websocket.send(json.dumps({"type": "game_start", "player": 1, "game_id": game_id}))
                self.waiting_player = None
            else:
                self.waiting_player = websocket
                if websocket.open:
                    await websocket.send(json.dumps({"type": "waiting"}))
                return

            async for message in websocket:
                await self.handle_message(websocket, game_id, message)

        except Exception as e:
            print(f"Error during connection handling: {e}")
            if websocket.open:
                await websocket.send(json.dumps({"type": "error", "message": str(e)}))
        finally:
            await self.handle_disconnect(websocket, game_id)


    async def handle_message(self, websocket, game_id, message):
        try:
            print(f"Received message: {message}")
            data = json.loads(message)
            game = self.games[game_id]
            player = game.players.index(websocket)

            if data['type'] == 'setup':
                game.setup_characters(player, data['characters'])
                if all(any(cell for cell in row) for row in game.board):
                    await self.broadcast_game_state(game_id)

            elif data['type'] == 'move':
                if game.is_valid_move(player, tuple(data['position']), data['direction']):
                    game.make_move(tuple(data['position']), data['direction'])
                    await self.broadcast_game_state(game_id)
                else:
                    await websocket.send(json.dumps({'type': 'error', 'message': 'Invalid move'}))
        except Exception as e:
            print(f"Error processing message: {e}")
            if websocket.open:
                await websocket.send(json.dumps({'type': 'error', 'message': str(e)}))

    async def handle_disconnect(self, websocket, game_id):
        if game_id in self.games:
            del self.games[game_id]
            print(f"Game {game_id} ended due to disconnection.")
        if self.waiting_player == websocket:
            self.waiting_player = None

    async def broadcast_game_state(self, game_id):
        game = self.games[game_id]
        state = game.get_state()
        await asyncio.gather(
            *[player.send(json.dumps({'type': 'state', 'state': state}))
              for player in game.players]
        )
        print(f"Broadcasted game state for game {game_id}")

async def main():
    server = GameServer()
    async with websockets.serve(server.handle_connection, "localhost", 8766):
        print("Server started on ws://localhost:8766")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
