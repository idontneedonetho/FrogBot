# modules.tic-tac-toe

from disnake import User, Interaction, ui, ButtonStyle
from disnake.ext import commands
import asyncio
import disnake
import random

class TicTacToeButton(ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=ButtonStyle.secondary, label="-")
        self.x = x
        self.y = y

    async def callback(self, interaction: Interaction):
        state: TicTacToe = self.view
        if state.board[self.x][self.y] != '-':
            await interaction.response.send_message('This spot is already taken!', ephemeral=True)
        elif interaction.user != state.current_player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
        else:
            state.board[self.x][self.y] = 'X' if state.current_player == state.users[0] else 'O'
            self.label = state.board[self.x][self.y]
            self.disabled = True
            if state.check_winner():
                await interaction.response.edit_message(content=f"{state.current_player.mention} wins!", view=None)
                return
            elif '-' not in [item for sublist in state.board for item in sublist]:
                await interaction.response.edit_message(content="It's a draw!", view=None)
                return
            state.switch_player()
            await interaction.response.edit_message(content=f"It's {state.current_player.mention}'s turn", view=state)
            if state.current_player == state.bot:
                await asyncio.sleep(0.5)
                await state.bot_move(interaction)

class TicTacToe(ui.View):
    def __init__(self, user1: User, user2: User, bot: User):
        super().__init__(timeout=180.0)
        self.users = [user1, user2]
        self.bot = bot
        self.current_player = user1
        self.board = [['-' for _ in range(3)] for _ in range(3)]
        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))
                if (x * 3 + y + 1) % 3 == 0 and x * 3 + y + 1 < 9:
                    self.add_item(ui.Button(style=ButtonStyle.secondary, label="\u200b", disabled=True))
                    self.add_item(ui.Button(style=ButtonStyle.secondary, label="\u200b", disabled=True))
    
    def switch_player(self):
        self.current_player = self.users[0] if self.current_player == self.users[1] else self.users[1]

    async def bot_move(self, interaction: Interaction):
        empty_spots = [(x, y) for x in range(3) for y in range(3) if self.board[x][y] == '-']
        if empty_spots:
            x, y = random.choice(empty_spots)
            self.board[x][y] = 'X' if self.current_player == self.users[0] else 'O'
            for item in self.children:
                if isinstance(item, TicTacToeButton) and item.x == x and item.y == y:
                    item.label = self.board[x][y]
                    item.disabled = True
                    break
            if self.check_winner():
                await interaction.edit_original_message(content=f"{self.current_player.mention} wins!", view=None)
                return
            elif '-' not in [item for sublist in self.board for item in sublist]:
                await interaction.edit_original_message(content="It's a draw!", view=None)
                return
            self.switch_player()
            await interaction.edit_original_message(content=f"It's {self.current_player.mention}'s turn", view=self)

    def check_winner(self):
        for row in self.board:
            if row.count(row[0]) == len(row) and row[0] != '-':
                return True
        for col in range(3):
            check = []
            for row in self.board:
                check.append(row[col])
            if check.count(check[0]) == len(check) and check[0] != '-':
                return True
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != '-':
            return True
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != '-':
            return True
        return False

@commands.slash_command()
async def tictactoe(ctx: disnake.ApplicationCommandInteraction, player2: disnake.User):
    player1 = ctx.author
    if player1.id == player2.id:
        await ctx.send("You cannot play against yourself!")
        return
    await ctx.send(f"It's {player1.mention}'s turn", view=TicTacToe(player1, player2, ctx.bot.user))

def setup(client):
    client.add_slash_command(tictactoe)