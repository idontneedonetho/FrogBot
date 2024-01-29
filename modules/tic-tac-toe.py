# tic-tac-toe.py

class TicTacToe:
    def __init__(self):
        self.board = [[" " for _ in range(3)] for _ in range(3)]
        self.current_turn = "X"
        self.game_over = False
        self.winner = None
      
    def get_board_str(self):
        board_str = ""
        for row in self.board:
            board_str += "|".join(row) + "\n"
            board_str += "-" * 5 + "\n"
        return board_str

    def make_move(self, row, col):
        row-=1
        col-=1
        if self.board[row][col] != " " or self.game_over:
            return False
        self.board[row][col] = self.current_turn
        if self.check_winner(row, col):
            self.game_over = True
            self.winner = self.current_turn
        else:
            self.current_turn = "O" if self.current_turn == "X" else "X"
        return True

    def check_winner(self, row, col):
        row-=1
        com-=1
        if all(self.board[row][i] == self.current_turn for i in range(3)):
            return True
        # Check the column
        if all(self.board[i][col] == self.current_turn for i in range(3)):
            return True
        # Check diagonals
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

@commands.command(name='start')
async def start_game(ctx):
    global game
    game = TicTacToe()
    await ctx.send("New game started! Use `ttt move [row] [col]` to make a move.")

@commands.command(name='move')
async def make_move(ctx, row: int, col: int):
    if row < 1 or row > 3 or col < 1 or col > 3:
        await ctx.send("Invalid move. Please choose row and column values between 1 and 3.")
        return

    if game.make_move(row, col):
        board_str = game.get_board_str()
        await ctx.send(f"Board updated:\n{board_str}")
        if game.game_over:
            await ctx.send(f"Game Over! Winner: {game.winner}")
        elif game.is_full():
            await ctx.send("Game Over! It's a draw.")
    else:
        await ctx.send("Invalid move. Try again.")

def setup(client):
  client.add_command(start_game)
  client.add_command(make_move)
