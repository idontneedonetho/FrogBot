# FrogBot
This has become a colabrative effor between a few of us to create the best bot we possibly can. The bot is still in a very rough state, things are constently breaking as it is.

Branches:
- Beta: This is the most updated branch and is constently being udpated and breaking.
- Dev: A go to point for PR's and anything else, it's the more stable of the newer branches. But not immune to breaking.
- Old: This is the first revision of the bot, there are a few broken things with it, wouldn't recommend using it.

I understand that Dev would normally be the one that's broken more than beta, however, for my work flow, I'd rather have the starting point for most people be "Dev", as it's mostly for PR's and IMO, PR's should be for the most stable branch.

So far features include:
- Automatic role assignment based on points
- Points assignment and removal
- Points tracking
- Add points via reactions
- Respond to different message
- Updating via commands
- AI LLM intergration via Google Gemini-pro(-vision) with OpenAi Chat-GPT 3.5 Turbo as a fall back.
- Image reginition via Gemini-pro-vision.
- Reply context chain for the LLM, you simply reply to the bots message to continue the chain.
- Very basic and very rough websearch

Things planned:
- Permanent Score board
- AI based filter to determin if a user needs assistance or not.
- Using websearch as context for responses for more accurate responeses.
- Using a non-finetune method for the LLM to pull more relevent info for OpenPilot/FrogPilot.

Special Thanks to:
- @[twilsonco](https://github.com/twilsonco)
- @nik.olas
- @cone_guy_03312
- @pkp24
- @mike854
- @[frogsgomoo](https://github.com/FrogAi)
- And those who help test in the FrogPilot discord server!
