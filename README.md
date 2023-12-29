# 🐸 FrogBot

[![GitHub issues](https://img.shields.io/github/issues/idontneedonetho/FrogBot)](https://github.com/idontneedonetho/FrogBot/issues)
[![GitHub stars](https://img.shields.io/github/stars/idontneedonetho/FrogBot)](https://github.com/idontneedonetho/FrogBot/stargazers)
[![License](https://img.shields.io/github/license/idontneedonetho/FrogBot)](https://github.com/idontneedonetho/FrogBot/blob/main/LICENSE)

**FrogBot** is a collaborative effort among a few of us to create the best bot possible. Please note that the bot is still in a very rough state, and things are constantly breaking.

## Table of Contents
- [Branches](#branches)
- [🚀 Current Features](#-current-features)
- [🛠️ Installation](#%EF%B8%8F-installation)
- [💬 Usage Examples](#-usage-examples)
- [🤝 Contributing](#-contributing)
- [📞 Contact](#-contact)
- [🙌 Acknowledgments](#-acknowledgments)

## Branches
- **🔥 Beta:** This is the most updated branch and is constantly being updated and may break.
- **🛠️ Dev:** A go-to point for PRs and other contributions, it's the more stable of the newer branches but not immune to breaking.
- **🕰️ Old:** This is the first revision of the bot; there are a few broken things with it, and we wouldn't recommend using it.

*Note: Dev is considered the starting point for most people, as it's primarily for PRs, and we aim to keep it stable.*

## 🚀 Current Features
- Automatic role assignment based on points
- Points assignment and removal
- Points tracking
- Add points via reactions
- Respond to different messages
- Updating via commands
- AI LLM integration via Google Gemini-pro(-vision) with OpenAI Chat-GPT 3.5 Turbo as a fallback
- Image recognition via Gemini-pro-vision
- Reply context chain for the LLM; you can simply reply to the bot's message to continue the conversation
- Very basic and rough web search

## 🛠️ Installation
To set up **FrogBot**, follow these steps:

### Prerequisites
- [Python](https://www.python.org/downloads/) (3.7+ recommended)
- [Git](https://git-scm.com/downloads)

### Clone the Repository
1. Clone the FrogBot repository to your local machine:
```bash
git clone https://github.com/idontneedonetho/FrogBot.git
cd FrogBot
```
### Python Dependencies
2. Install Python dependencies:
```bash
pip install discord.py discord.ext asyncio aiohttp nltk trafilatura requests
pip install googlesearch-python python-dotenv google openai pillow
```
### Configure Your Bot
3. Create a `.env` file in the root directory of the bot and add your bot token and other configuration details:
```makefile
DISCORD_TOKEN=YOUR_BOT_TOKEN
OTHER_CONFIG_KEY=OTHER_CONFIG_VALUE
```
### Running the bot
4. Start the bot:
```
python bot.py
```
Please note that installation instructions may, be wrong as I might have forgotten something, or differ for the **Beta branch**. Check the branch-specific instructions for Beta if you're using that branch.

The bot should now be up and running, ready to serve your Discord server! Customize it further to suit your needs.

For more advanced configuration or deployment options, refer to the official documentation for each library and tool you've imported.

## 💬 Usage Examples
- To add points to a user: `@{bot name} add {number} points @{user}`
- To remove points from a user: `@{bot name} remove {number} points @{user}`
- To check a user's points: `@{bot name} check points @{user}`
- Ask questions or seek information by mentioning the bot in your message: `@{bot name} What's the weather today?`
- Use `@{bot name} help` for more information on available commands.

## 🤝 Contributing
Contributions to FrogBot are welcome! Follow these steps to contribute:
1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Make your changes and commit them.
4. Push your changes to your forked repository.
5. Submit a pull request to the main repository.

## 📞 Contact
For support and questions, join our Discord server: [FrogBot Discord](https://l.linklyhq.com/l/1t3Il)

## 🙌 Acknowledgments
### Thanks-
- [twilsonco](https://github.com/twilsonco)
- nik.olas
- cone_guy_03312
- pkp24
- mike854
- [frogsgomoo](https://github.com/FrogAi)

## 🙌 Libraries and Tools Used
FrogBot relies on the following external libraries and tools to power its functionality:

- [discord.py](https://pypi.org/project/discord.py/): A popular Python library for creating Discord bots.
- [nltk](https://www.nltk.org/): The Natural Language Toolkit for Python, used for natural language processing.
- [trafilatura](https://pypi.org/project/trafilatura/): A Python library for extracting text from web pages.
- [requests](https://pypi.org/project/requests/): A Python library for making HTTP requests.
- [googlesearch-python](https://pypi.org/project/googlesearch-python/): A Python library for performing Google searches.
- [aiohttp](https://docs.aiohttp.org/): An asynchronous HTTP client/server framework.
- [python-dotenv](https://pypi.org/project/python-dotenv/): A Python library for reading environment variables from a `.env` file.
- [google](https://github.com/googleapis/google-api-python-client): Google APIs Client Library for Python.
- [openai](https://pypi.org/project/openai/): Python client library for OpenAI GPT models.
- [pillow](https://pypi.org/project/Pillow/): The Python Imaging Library, used for image processing.

These external libraries and tools are essential for enabling FrogBot's features and capabilities. Make sure to review their documentation for further details on usage and functionality.

*Disclaimer this README file was written mostly by ChatGPT 3.5 Turbo.*
