# 🐸 FrogBot

[![GitHub issues](https://img.shields.io/github/issues/idontneedonetho/FrogBot)](https://github.com/idontneedonetho/FrogBot/issues)
[![GitHub stars](https://img.shields.io/github/stars/idontneedonetho/FrogBot)](https://github.com/idontneedonetho/FrogBot/stargazers)
[![License](https://img.shields.io/github/license/idontneedonetho/FrogBot)](https://github.com/idontneedonetho/FrogBot/blob/main/LICENSE)

**FrogBot** is a collaborative effort among a few of us to create the best bot possible. Please note that the bot is still in a very rough state, and things are constantly breaking.

## Table of Contents
- [Branches](#branches)
- [🚀 Current Features](#-current-features)
- [💬 Usage Examples](#-usage-examples)
- [🧱 DLM](#-dlm)
- [🤝 Contributing](#-contributing)
- [📞 Connect](#-connect)
- [🙌 Acknowledgments](#-acknowledgments)

## Branches
- **🔥 Beta:** This is the most updated branch and is constantly being updated and may break.
- **🛠️ Dev:** A go-to point for PRs and other contributions, it's the more stable of the newer branches but not immune to breaking.
- **🕰️ Old:** This is the first revision of the bot; there are a few broken things with it, and we wouldn't recommend using it.

*Note: Dev is considered the starting point for most people, as it's primarily for PRs, and we aim to keep it stable.*

## 🚀 Current Features
- [DLM](#-dlm)
- Automatic role assignment based on points
- Points assignment and removal
- Points tracking
- Add points via reactions
- Respond to different messages
- Updating via commands
- AI LLM integration via GPT 4 with OpenAI, and Google Gemini-Pro as a fallback
- Reply context chain for the LLM; you can simply reply to the bot's message to continue the conversation
- Very basic and rough web search

## 💬 Usage Examples
- To add points to a user: `@{bot name} add {number} points @{user}`
- To remove points from a user: `@{bot name} remove {number} points @{user}`
- To check a user's points: `@{bot name} check points @{user}`
- Ask questions or seek information by mentioning the bot in your message: `@{bot name} What's the weather today?`
- Use `@{bot name} help` for more information on available commands.

<h2 id="dlm">🧱 DLM</h2>
Dynamically Loaded Modules, or DLM for short, is a different way to add to the bot. Why use this when discord.py has Cogs? Cogs, for me, seem to be hit or miss, and we needed something more robust, something that wouldn't need us to change any other code to work.
Now it isn't perfect, but it's the best we can get and allows most modules to be pretty freeform. If you want to add a feature, simply write a new .py file and make it a PR! For now, I'll work directly with devs of modules to make sure DLM works, and works right.
Hopefully in the future, PR's will be automated to an extent. We'll see... For now, this is where we are.

## 🤝 Contributing
Contributions to FrogBot are welcome! Follow these steps to contribute:
1. Create a DLM.
2. Create a new PR for it.
3. Profit???

## 📞 Connect
For support and questions, join our Discord server: [FrogPilot Discord](https://l.linklyhq.com/l/1t3Il).

*Just go-to `#development-chat`, and join the `#FrogBot Dev` thread!*

## 🙌 Acknowledgments
### Thanks-
- Joeslinky - For their GPT 4 API KEY!
- [twilsonco](https://github.com/twilsonco)
- nik.olas
- cone_guy_03312
- pkp24
- mike854
- [frogsgomoo](https://github.com/FrogAi)
- And all those that help break to test the bot

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
