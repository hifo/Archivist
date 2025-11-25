"""
A Discord bot client using discord.py.
Logs in and prints messages received.
"""
import os
import discord
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from dotenv import load_dotenv


# Load local .env (if present) into the environment, then read token
load_dotenv()

TOKEN = os.environ.get('DISCORD_TOKEN')

message = None

class MyClient(discord.Client):
    """
    Custom Discord client that logs events to the console.
    """
    async def on_ready(self):
        """
        Called when the bot has successfully connected to Discord.
        """
        print(f'Logged on as {self.user}!')
    
    async def on_message(self, message):
        """
        Handles incoming messages and prints author and content.
        Args:
            message (discord.Message): The message received.
        """

        if message.content.startswith('!save'):
            # Extract the text payload after the command
            content_str = message.content[len('!save '):].strip()
            if not content_str:
                await message.channel.send('Please provide text to save. Usage: `!save your text here`')
                return

            # Wrap saved object with metadata about who saved it
            try:
                timestamp = message.created_at.isoformat()
            except (AttributeError, TypeError, ValueError):
                timestamp = str(getattr(message, 'created_at', None))

            saved_entry = {
                'author': str(message.author),
                'timestamp': timestamp,
                'payload': content_str,
            }

            data_file = 'data.json'
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        data = existing
                    else:
                        data = [existing]
            except FileNotFoundError:
                data = []
            except json.JSONDecodeError:
                # Corrupted file — overwrite with a fresh list
                data = []

            data.append(saved_entry)
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            await message.channel.send('Saved to `data.json`.')

        if message.content.startswith('!load'):
            # Allow optional timezone argument: e.g. `!load Europe/Berlin`
            tz_arg = message.content[len('!load'):].strip()
            tz_obj = None
            if tz_arg:
                try:
                    tz_obj = ZoneInfo(tz_arg)
                except ZoneInfoNotFoundError:
                    await message.channel.send(f'Unknown timezone: `{tz_arg}`. Use an IANA timezone name like `Europe/Berlin`.')
                    return
            data_file = 'data.json'
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Normalize to list
                if not isinstance(data, list):
                    data = [data]

                # Group entries by author, preserving full entry metadata.
                grouped = {}
                for entry in data:
                    if isinstance(entry, dict) and 'author' in entry:
                        key = entry.get('author') or 'unknown'
                        grouped.setdefault(key, []).append(entry)
                    else:
                        # Legacy entry: wrap into standard shape
                        grouped.setdefault('unknown', []).append({
                            'author': 'unknown',
                            'timestamp': None,
                            'payload': entry,
                        })

                # Build a user-friendly textual representation per author
                parts = []
                for author, entries in grouped.items():
                    parts.append(f'Author: {author} ({len(entries)} message(s))')
                    for idx, ent in enumerate(entries, start=1):
                        ts = ent.get('timestamp') if isinstance(ent, dict) else None
                        # Make timestamps human-readable
                        human_ts = None
                        if ts:
                            try:
                                # Parse ISO format timestamp
                                dt = datetime.fromisoformat(ts)
                                # If timestamp is naive, assume it is UTC
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                # Convert to requested timezone (or server local if none)
                                if tz_obj is not None:
                                    local_dt = dt.astimezone(tz_obj)
                                else:
                                    local_dt = dt.astimezone()
                                human_ts = local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                            except ValueError:
                                human_ts = ts
                        payload = ent.get('payload') if isinstance(ent, dict) and 'payload' in ent else (ent if isinstance(ent, dict) else ent)
                        # Display payload first, then the timestamp
                        parts.append(f'  {idx}) {json.dumps(payload, ensure_ascii=False)}')
                        parts.append(f'       Timestamp: {human_ts}')
                    parts.append('')

                friendly_text = '\n'.join(parts)

                async def _send_paginated(channel, header, text, lang=None):
                    # Discord message limit is 2000 chars. Keep a safe margin for fences and header.
                    max_chunk = 1900
                    for i in range(0, len(text), max_chunk):
                        chunk = text[i:i+max_chunk]
                        if i == 0:
                            if lang:
                                content = f"{header}\n```{lang}\n{chunk}\n```"
                            else:
                                content = f"{header}\n{chunk}"
                        else:
                            if lang:
                                content = f"```{lang}\n{chunk}\n```"
                            else:
                                content = chunk
                        await channel.send(content)

                await _send_paginated(message.channel, 'Saved messages:', friendly_text)
            except FileNotFoundError:
                await message.channel.send('No data found. `data.json` does not exist.')
            except json.JSONDecodeError:
                await message.channel.send('Error reading `data.json`. The file may be corrupted.')

intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)

if not TOKEN:
    print('ERROR: DISCORD_TOKEN environment variable is not set.\n'
          'Set it before running this bot, for example in PowerShell:')
    print('  $env:DISCORD_TOKEN = "<your-token>"')
    raise SystemExit(1)

client.run(TOKEN)
