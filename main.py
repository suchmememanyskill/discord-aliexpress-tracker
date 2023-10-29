import discord
from discord.ext import commands

import asyncio
import os
import logging
import traceback
import sys
import json
import aiohttp
import time
import extract

intents = discord.Intents.none()
intents.members = True
logger = logging.getLogger('discord.bot')
token = os.getenv('BOT_TOKEN')
if token is None:
    raise Exception('BOT_TOKEN env var not set')

class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.ali_group = discord.app_commands.Group(name='ali', description='Manage aliexpress tracking codes')
        self.tree.add_command(self.ali_group)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyClient(intents=intents)

USER_TRACKING_CODES = {}

def load_tracking_codes():
    global USER_TRACKING_CODES

    if not os.path.exists('tracking.json'):
        return

    with open('tracking.json', 'r') as fp:
        USER_TRACKING_CODES = json.load(fp)

def save_tracking_codes():
    with open('tracking.json', 'w') as fp:
        json.dump(USER_TRACKING_CODES, fp)

def add_tracking_code(user_id : str, code : str, name : str):
    if user_id not in USER_TRACKING_CODES:
        USER_TRACKING_CODES[user_id] = {}
    
    USER_TRACKING_CODES[user_id][code] = {
        "name": name,
        "last_status": ""
    }

    save_tracking_codes()

def remove_tracking_code(user_id : str, code : str):
    if user_id not in USER_TRACKING_CODES:
        return
    
    if code not in USER_TRACKING_CODES[user_id]:
        return
    
    del USER_TRACKING_CODES[user_id][code]

    save_tracking_codes()

def update_tracking_code(user_id : str, code : str, status : str):
    if user_id not in USER_TRACKING_CODES:
        return
    
    if code not in USER_TRACKING_CODES[user_id]:
        return
    
    USER_TRACKING_CODES[user_id][code]["last_status"] = status

    save_tracking_codes()

def get_tracking_code_data(user_id : str, code : str):
    if user_id not in USER_TRACKING_CODES:
        return None
    
    if code not in USER_TRACKING_CODES[user_id]:
        return None
    
    return USER_TRACKING_CODES[user_id][code]

def get_all_user_tracking_codes(user_id : str):
    if user_id not in USER_TRACKING_CODES:
        return None
    
    return USER_TRACKING_CODES[user_id]

def get_all_tracking_codes():
    return sum([list(get_all_user_tracking_codes(x).keys()) for x in USER_TRACKING_CODES], [])

load_tracking_codes()

@bot.ali_group.command(name="add", description="Add a tracking code")
async def ali_add(interaction: discord.Interaction, code : str, name : str, user : discord.User = None):
    code = code.strip()
    name = name.strip()
    add_tracking_code(str((user or interaction.user).id), code, name)
    message = f"Added tracking code '{code}' as {name}"
    if (user is not None):
        message += "\nThe user you added a tracking code to is not you. You will not receive updates for this code."

    await interaction.response.send_message(message, ephemeral=True)

    if (user is not None):
        user_dm_channel = user.dm_channel
        if user_dm_channel is None:
            user_dm_channel = await user.create_dm()
        
        await user_dm_channel.send(f"{interaction.user.mention} ({interaction.user.name}) added a tracking code on your behalf: '{code}' as {name}")

async def codes_autocomplete(interaction: discord.Interaction, current: str) -> list[discord.app_commands.Choice[str]]:
    user_id = str(interaction.user.id)
    codes = get_all_user_tracking_codes(user_id)

    try:
        result = [
            discord.app_commands.Choice(name=codes[x]['name'], value=x)
            for x in codes if current.lower() in codes[x]['name'].lower()
        ]
        print(result)
    except Exception as e:
        result = []
        print(str(e))

    return result

@bot.ali_group.command(name="remove", description="Remove a tracking code")
@discord.app_commands.autocomplete(code=codes_autocomplete)
async def ali_remove(interaction: discord.Interaction, code : str):
    code = code.strip()
    remove_tracking_code(str(interaction.user.id), code)
    await interaction.response.send_message(f"Removed tracking code '{code}'", ephemeral=True)

async def fetch_tracking_data():
    while True:
        logger.info("Fetching tracking data")
        try:
            e = extract.extract_tracking_data(get_all_tracking_codes())
            p = extract.parse_tracking_data(e)

            def find(code : str):
                for x in p:
                    if x.id == code:
                        return x
                    
                return None
            
            for user_id in USER_TRACKING_CODES:
                embeds = []
                removals = []

                for code in USER_TRACKING_CODES[user_id]:
                    tracking = find(code)
                    data = get_tracking_code_data(user_id, code)
                    if tracking is None:
                        continue

                    if (tracking.get_last_status() == data["last_status"]):
                        continue

                    embed = discord.Embed(title=data['name'], description=str(tracking))
                    embeds.append(embed)

                    if (tracking.get_last_status() == "Delivered"):
                        removals.append(code)
                        embed.set_footer(text="Package seems to be delivered, removing!")

                    update_tracking_code(user_id, code, tracking.get_last_status())

                for x in removals:
                    remove_tracking_code(user_id, x)

                if len(embeds) <= 0:
                    continue

                user = bot.get_user(int(user_id))
                if user is None:
                    user = await bot.fetch_user(int(user_id))
                
                user_dm_channel = user.dm_channel
                if user_dm_channel is None:
                    user_dm_channel = await user.create_dm()
                
                await user_dm_channel.send(embeds=embeds)

        except Exception as e:
            print(traceback.format_exc())
            logger.error(f"Failed fetching tracking data: {str(e)}")

        await asyncio.sleep(60 * 60 * 2) # 2 hours

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')
    asyncio.create_task(fetch_tracking_data())

bot.run(token)
