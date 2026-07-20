# 🥫 Rob
A fun bot for your Discord server that can join the conversation!
Just ping him with a message, and he'll respond back just as if he was another one of yours! 
Share opinions, laugh together, and level up your server with a bot that can talk, send/get custom letters to/from your trusted servers, and automatically get the chat back on track when it's inactive!

[Invite Rob to your server now for $0.00!](https://discord.com/oauth2/authorize?client_id=1344543448719429673)

# Setup guide
1. Invite Rob to your server.
2. Optionally, you can create the `• RobAdmin` role and assign it to non-admin people you want changing Rob's settings.
3. Take a moment to use the `#!option <option> <value>` command to change Rob's settings to your liking. Available options and what they do:
    - `randomlyMessage` (values: **enable/disable**) -- Allows the bot to send an unprompted message at a random time when the chat is inactive. - Default is **disable**
    - `responseFrequency` (values: **a number from 1-100**, default **4**) -- Controls the chances of Rob responding to a message without being pinged to do so (a higher number means more often, recommended values are 0-4 if your server isn't Rob-centric) - Default is **4**
    - `listen` (values: **enable/disable**) -- Turns the bot on when enabled or off when disabled. - Default is **enable**
    - `dumb` (values: **enable/disable**) -- Controls whether to generate messages locally instead of using groqcloud's API, which may produce less coherent responses and may not use a full-fat AI model all the time. **This is currently an UNSTABLE feature as it may make the bot faster, slower, or not work at all.** - Default is **disable**
    - `mailChannel` (values: **channel name starting with #**) -- Sets the channel to use for receiving letters from other servers. - Auto-detects your general channel by default.
4. Send your first message to Rob by @mentioning him!

# Commands
## Mail:
- `#!address` - Shows your server's robmail address.
- `#!trust <address>` (admin) - Trusts another server's address, allowing them to send you letters. Must be run on both your and their server.
- `#!untrust <address>` (admin) - Stops trusting another server's address, blocking them from sending you letters.
- `#!phonebook` - Presents all addresses trusted by the current server.
- `#!send <address> <message>` - Sends a letter to a specified robmail address.
## Behavior overrides:
- `#!owobonk` - Hits Rob with the magic owo stick that temporarily uwuifies his responses.
## Misc:
- `#!help` - Sends a link to Rob's official website.
- `#!about` - Shows bot credits and interaction stats.
- `#!dadjoke` - Sends a random joke from the [icanhazadadjoke](https://icanhazdadjoke.com/) API.
- `#!search` - Searches for stuff on the web using DuckDuckGo and provides a Rob-certified™ summary.

# Development setup
1. Clone this repo and install requirements
```bash
git clone https://github.com/Dogo6647/rob.git
cd rob
pip install -r requirements.txt
```

2. Edit .env.example with your preferred text editor and rename it to .env

3. Run the bot
```
python3 src/main.py
```
