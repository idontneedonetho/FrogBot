# tic-tac-toe.py

class TicTacToe:
    def __init__(self):
        self.board = [[" " for _ in range(3)] for _ in range(3)]
        self.player_x = None
        self.player_o = None
        self.current_turn = "X"
        self.game_over = False
        self.winner = None

    def set_players(self, player_x, player_o):
        self.player_x = player_x
        self.player_o = player_o

    def get_board_str(self):
        board_str = ""
        for i in range(3):
            for j in range(3):
                cell = self.board[i][j]
                if cell == " ":
                    cell = str(i * 3 + j + 1)  # Display cell number if empty
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
        else:
            self.current_turn = "O" if self.current_turn == "X" else "X"
        return True

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

import discord
from discord.ext import commands

game = TicTacToe()

@commands.command(name='ttt start')
async def start_game(ctx, player_x: discord.Member, player_o: discord.Member):
    global game
    game = TicTacToe()
    game.set_players(player_x.id, player_o.id)
    initial_board = "``` 1 | 2 | 3\n-----------\n 4 | 5 | 6\n-----------\n 7 | 8 | 9```"
    await ctx.send(f"New game started between {player_x.mention} (X) and {player_o.mention} (O)! Use `ttt move [number]` to make a move. {player_x.mention} goes first.\n{initial_board}")

@commands.command(name='ttt move')
async def make_move(ctx, num: int):
    player_id = ctx.author.id
    valid_move, message = game.make_move(player_id, num)
    if valid_move:
        board_str = game.get_board_str()
        next_player = game.player_x if game.current_turn == "O" else game.player_o
        next_player_mention = ctx.guild.get_member(next_player).mention
        await ctx.send(f"Board updated:\n```{board_str}```\nNext turn: {next_player_mention}")
        if game.game_over:
            winner_mention = ctx.guild.get_member(game.winner).mention
            await ctx.send(f"Game Over! Winner: {winner_mention}")
        elif game.is_full():
            await ctx.send("Game Over! It's a draw.")
    else:
        await ctx.send(message)

def setup(client):
  client.add_command(start_game)
  client.add_command(make_move)
