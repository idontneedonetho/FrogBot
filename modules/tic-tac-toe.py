# tic-tac-toe.py

import discord
from discord.ext import commands
import asyncio

client = commands.Bot(command_prefix=None)

class TicTacToe:
    def __init__(self):
        self.board = [[" " for _ in range(3)] for _ in range(3)]
        self.player_x = None
        self.player_o = None
        self.current_turn = "X"
        self.game_over = False
        self.winner = None
        self.message_id = None

    def set_players(self, player_x, player_o):
        self.player_x = player_x
        self.player_o = player_o

    def get_board_str(self):
        board_str = ""
        for i in range(3):
            for j in range(3):
                cell = self.board[i][j]
                if cell == " ":
                    cell = str(i * 3 + j + 1)
                board_str += f" {cell} "
                if j < 2:
                    board_str += "|"
            if i < 2:
                board_str += "\n-----------\n"
        return board_str

    def make_move(self, player, num):
        if player != (self.player_x if self.current_turn == "X" else self.player_o):
            return False, "It's not your turn!"
        if num < 1 or num > 9 or self.game_over:
            return False, "Invalid move. Must be a number between 1 and 9."
        row = (num - 1) // 3
        col = (num - 1) % 3
        if self.board[row][col] != " ":
            return False, "Cell is already occupied."
        self.board[row][col] = self.current_turn
        if self.check_winner(row, col):
            self.game_over = True
            self.winner = self.current_turn
            return True, "Player wins."
        else:
            self.current_turn = "O" if self.current_turn == "X" else "X"
            return True, "Valid move :)"

    def check_winner(self, row, col):
        if all(self.board[row][i] == self.current_turn for i in range(3)):
            return True
        if all(self.board[i][col] == self.current_turn for i in range(3)):
            return True
        if row == col and all(self.board[i][i] == self.current_turn for i in range(3)):
            return True
        if row + col == 2 and all(self.board[i][2 - i] == self.current_turn for i in range(3)):
            return True
        return False

    def is_full(self):
        return all(self.board[row][col] != " " for row in range(3) for col in range(3))

    def timeout_game(self):
        if not self.game_over:
            self.game_over = True
            return True
        return False

games = {}

@commands.command(name='ttt_start')
async def start_game(ctx, player_x: discord.Member, player_o: discord.Member):
    global games
    game = TicTacToe()
    game.set_players(player_x.id, player_o.id)
    initial_board = "``` 1 | 2 | 3\n-----------\n 4 | 5 | 6\n-----------\n 7 | 8 | 9```"
    game_message = await ctx.send(f"New game started between {player_x.mention} (X) and {player_o.mention} (O)! Reply to this message with `ttt_move [number]` to make a move. {player_x.mention} goes first.\n{initial_board}")
    games[game_message.id] = game
    game.message_id = game_message.id

    async def game_timeout():
        await asyncio.sleep(3600)
        if game.timeout_game():
            await ctx.send("Game Over! The game has timed out after 1 hour.")

    asyncio.create_task(game_timeout())

def setup(client):
    client.add_command(start_game)

@client.event
async def on_message(message):
    global games
    if message.reference and message.reference.message_id in games:
        game_message_id = message.reference.message_id
        game = games[game_message_id]

        if message.content.startswith("ttt_move"):
            try:
                _, num_str = message.content.split()
                num = int(num_str)
                player_id = message.author.id
                valid_move, response_message = game.make_move(player_id, num)

                if valid_move:
                    board_str = game.get_board_str()
                    if game.game_over:
                        winner_mention = message.guild.get_member(game.winner).mention
                        new_message = await message.channel.send(f"Game Over! Winner: {winner_mention}\n```{board_str}```")
                        del games[game_message_id]
                    else:
                        next_player = game.player_o if game.current_turn == "O" else game.player_x
                        next_player_mention = message.guild.get_member(next_player).mention
                        new_message = await message.channel.send(f"Board updated:\n```{board_str}```\nNext turn: {next_player_mention}")
                        if game.is_full():
                            await message.channel.send("Game Over! It's a draw.")
                            del games[game_message_id]
                        else:
                            games.pop(game_message_id)
                            game.message_id = new_message.id
                            games[game.message_id] = game
                else:
                    await message.channel.send(response_message)
            except (ValueError, IndexError):
                await message.channel.send("Invalid command format. Use 'ttt_move [number]'.")

    await client.process_commands(message)
