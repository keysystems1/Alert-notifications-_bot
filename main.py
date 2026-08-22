import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, json, aiohttp
from flask import Flask
import threading, asyncio

TOKEN = os.getenv("DISCORD_TOKEN")

ROOM_RT = 1537833593919901706
ROOM_MT = 1540466423854268537
ROLE_ID = 1538971924523253961

STREAMERS_RT = ["hook","seagull","drb7h","f1aisal","fhlwy","peerless","imonkey_d","abo8alyy","abo_khrbaa","id7o","s5b","okb8","taf86","aymnalsatam"]
STREAMERS_MT = ["firas","osamah","abokhaled_sa","abokyan","abdulrhman","majah92","brof2","tmnaa","7omah","sxb","abuswe7l"]
ALL_STREAMERS = STREAMERS_RT + STREAMERS_MT

OWNER_ROLE_ID = 1537833274875838515

def only_owner_role(interaction: discord.Interaction):
    if isinstance(interaction.user, discord.Member):
        for r in interaction.user.roles:
            if r.id == OWNER_ROLE_ID:
                return True
    return False

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
live_cache = {}

async def get_kick_info(slug):
    urls = [
        f"https://kick.com/api/v2/channels/{slug}",
        f"https://kick.com/api/v1/channels/{slug}",
        f"https://kick.com/api/v2/channels/{slug}/chatroom"
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": f"https://kick.com/{slug}",
        "Origin": "https://kick.com"
    }
    for url in urls:
        try:
            async with aiohttp.ClientSession(headers=headers) as s:
                async with s.get(url, timeout=10) as r:
                    if r.status == 200:
                        data = await r.json()
                        if "user" in data or "livestream" in data:
                            ls = data.get("livestream")
                            last = data.get("last_broadcast") or {}
                            is_live = ls is not None
                            if not is_live and data.get("is_live"):
                                is_live = True
                            title = ""
                            if ls:
                                title = ls.get("session_title") or ""
                            if not title and last.get("session_title"):
                                title = last["session_title"]
                            if not title:
                                title = data.get("session_title") or "No Title"
                            cat = {}
                            if ls and ls.get("categories"):
                                cat = ls["categories"][0]
                            elif last.get("categories"):
                                cat = last["categories"][0]
                            thumb = None
                            if ls and ls.get("thumbnail"):
                                t = ls["thumbnail"]
                                thumb = t.get("url") if isinstance(t, dict) else t
                            return {
                                "username": data.get("slug") or slug,
                                "profile_pic": (data.get("user") or {}).get("profile_pic") or data.get("profile_pic"),
                                "is_live": is_live,
                                "title": title,
                                "category": cat.get("name") or (data.get("category") or {}).get("name"),
                                "category_thumb": cat.get("thumbnail"),
                                "thumbnail": thumb or data.get("thumbnail")
                            }
        except Exception as e:
            print(f"try {url} fail {e}")
            continue
    try:
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"https://kick.com/{slug}", timeout=10) as r:
                text = await r.text()
                is_live = '"is_live":true' in text or '"livestream":{' in text and '"id":' in text
                if 'LIVE' in text[:5000] or is_live:
                    return {
                        "username": slug,
                        "profile_pic": None,
                        "is_live": True,
                        "title": "Live on Kick!",
                        "category": "Live",
                        "category_thumb": None,
                        "thumbnail": None
                    }
    except Exception as e:
        print(f"page check fail {e}")
    return None

class KickView(discord.ui.View):
    def __init__(self, slug):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=f"Kick.com/{slug}", url=f"https://kick.com/{slug}", emoji="🔗"))

@tasks.loop(seconds=30)
async def check_kick():
    print("--- CHECKING ---")
    for slug in ALL_STREAMERS:
        info = await get_kick_info(slug)
        if not info:
            print(f"{slug}: API blocked")
            continue
        was = live_cache.get(slug, False)
        target_room = ROOM_RT if slug in STREAMERS_RT else ROOM_MT
        print(f"{slug}: live={info['is_live']} was={was} -> {target_room}")
        if info["is_live"] and not was:
            live_cache[slug] = True
            ch = bot.get_channel(target_room)
            if not ch:
                for g in bot.guilds:
                    ch = g.get_channel(target_room)
                    if ch:
                        break
            if ch:
                embed = discord.Embed(description=f"{info['title']}", color=0x53FC18)
                embed.set_author(name=f"{slug} LIVE!")
                if info["thumbnail"]:
                    embed.set_image(url=info["thumbnail"])
                if info["category"]:
                    embed.set_footer(text=info["category"])
                try:
                    await ch.send(content=f"<@&{ROLE_ID}> 🟢 **{slug} فتح بث!**", embed=embed, view=KickView(slug))
                    print(f"SENT {slug}")
                    await asyncio.sleep(2)
                except Exception as e:
                    print(e)
        elif not info["is_live"]:
            live_cache[slug] = False

@bot.event
async def on_ready():
    print(f"✅ READY {bot.user}")
    try:
        await bot.tree.sync()
    except:
        pass
    if not check_kick.is_running():
        check_kick.start()

@bot.tree.command(name="كلاش", description="فحص")
@app_commands.describe(الرابط="https://kick.com/id7o")
@app_commands.check(only_owner_role)
async def clash(interaction: discord.Interaction, الرابط: str):
    slug = الرابط.split("kick.com/")[-1].split("/")[0].lower().strip()
    await interaction.response.send_message(f"⏳ افحص `{slug}`...", ephemeral=True)
    info = await get_kick_info(slug)
    if not info:
        return await interaction.followup.send(f"❌ Kick حاجب سيرفر Render - جرب بعد شوي", ephemeral=True)
    embed = discord.Embed(description=info['title'], color=0x53FC18 if info['is_live'] else 0xED4245)
    if info["thumbnail"]:
        embed.set_image(url=info["thumbnail"])
    await interaction.followup.send(f"**{slug}** - {'🔴 لايف' if info['is_live'] else '⚫️ اوفلاين'}", embed=embed, view=KickView(slug), ephemeral=True)

@bot.tree.command(name="فحص_الان", description="ارسل اللي فاتحين غصب")
@app_commands.check(only_owner_role)
async def force_check(interaction: discord.Interaction):
    await interaction.response.send_message("⏳ افحص... كل واحد برسالة لحالها", ephemeral=True)
    sent_rt = []
    sent_mt = []
    for slug in ALL_STREAMERS:
        info = await get_kick_info(slug)
        if info and info['is_live']:
            target_room = ROOM_RT if slug in STREAMERS_RT else ROOM_MT
            ch = bot.get_channel(target_room) or next((g.get_channel(target_room) for g in bot.guilds if g.get_channel(target_room)), None)
            if ch:
                embed = discord.Embed(description=info['title'], color=0x53FC18)
                embed.set_author(name=f"{slug} LIVE!")
                if info["thumbnail"]:
                    embed.set_image(url=info["thumbnail"])
                await ch.send(content=f"<@&{ROLE_ID}> 🟢 **{slug}** لايف!", embed=embed, view=KickView(slug))
                (sent_rt if slug in STREAMERS_RT else sent_mt).append(slug)
                live_cache[slug] = True
                await asyncio.sleep(2)
    await interaction.followup.send(f"✅ RT ({len(sent_rt)}): {', '.join(sent_rt) or '0'}\nMT ({len(sent_mt)}): {', '.join(sent_mt) or '0'}", ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        try:
            await interaction.response.send_message("❌ هذا الامر بس لرول الاونر", ephemeral=True)
        except:
            pass

app = Flask('')
@app.route('/')
def home():
    return "OK"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
bot.run(TOKEN)
                    
