import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, json, aiohttp
from flask import Flask
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "kick_data.json"
CHANNEL_ID = 1537833593919901706

STREAMERS = ["hook","seagull","drb7h","f1aisal","fhlwy","peerless","imonkey_d","abo8alyy","abo_khrbaa","id7o","s5b","okb8","taf86","firas"]

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE,"r") as f: return json.load(f)
        except: return {}
    return {}
def save_data(d):
    with open(DATA_FILE,"w") as f: json.dump(d,f,indent=2)

kick_data = load_data()
live_cache = {}

@bot.event
async def on_ready():
    print(f"✅ BOT READY: {bot.user} | Guilds: {len(bot.guilds)}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"sync error {e}")
    if not check_kick.is_running():
        check_kick.start()

async def get_kick_info(slug):
    headers = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
    try:
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"https://kick.com/api/v2/channels/{slug}",timeout=12) as r:
                if r.status==200:
                    data=await r.json()
                    ls=data.get("livestream")
                    last=data.get("last_broadcast") or {}
                    cat={}
                    if ls and ls.get("categories"): cat=ls["categories"][0]
                    elif last.get("categories"): cat=last["categories"][0]
                    thumb=None
                    if ls and ls.get("thumbnail"):
                        t=ls["thumbnail"]; thumb=t.get("url") if isinstance(t,dict) else t
                    if not thumb and last.get("thumbnail"):
                        t=last["thumbnail"]; thumb=t.get("url") if isinstance(t,dict) else t
                    return {
                        "username":data.get("slug") or slug,
                        "profile_pic":(data.get("user") or {}).get("profile_pic"),
                        "is_live": ls is not None,
                        "title": (ls.get("session_title") if ls else "") or last.get("session_title") or "No Title",
                        "category": cat.get("name"),
                        "category_thumb": cat.get("thumbnail"),
                        "thumbnail": thumb
                    }
    except Exception as e:
        print(f"get_kick_info {slug} error {e}")
    return None

class KickView(discord.ui.View):
    def __init__(self,slug):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=f"Kick.com/{slug}",url=f"https://kick.com/{slug}",emoji="🔗"))
        self.add_item(discord.ui.Button(label="Watch VOD",url=f"https://kick.com/{slug}/videos",emoji="🔄"))

@tasks.loop(seconds=45)
async def check_kick():
    print("--- CHECKING KICK ---")
    for slug in STREAMERS:
        info = await get_kick_info(slug)
        if not info:
            print(f"{slug}: no info")
            continue
        was = live_cache.get(slug, False)
        print(f"{slug}: live={info['is_live']} was={was}")
        if info["is_live"] and not was:
            live_cache[slug]=True
            ch = bot.get_channel(CHANNEL_ID)
            if not ch:
                for g in bot.guilds:
                    ch = g.get_channel(CHANNEL_ID)
                    if ch: break
            if ch:
                embed=discord.Embed(description=f"{info['title']}",color=0x53FC18)
                embed.set_author(name=f"{info['username']} LIVE! {info['username']} is now live on Kick!",icon_url=info["profile_pic"])
                if info["thumbnail"]: embed.set_image(url=info["thumbnail"])
                if info["category"]: embed.set_footer(text=f"{info['category']} | {info['username']}")
                if info["category_thumb"]: embed.set_thumbnail(url=info["category_thumb"])
                try:
                    await ch.send(content=f"@everyone 🟢 **{slug} فتح بث!**\n{info['title']}",embed=embed,view=KickView(slug))
                    print(f"✅ SENT {slug}")
                except Exception as e:
                    print(f"❌ send fail {slug}: {e}")
        elif not info["is_live"]:
            live_cache[slug]=False

@bot.tree.command(name="كلاش",description="فحص ستريمر Kick")
@app_commands.describe(الرابط="رابط القناة مثل https://kick.com/id7o")
async def clash(interaction:discord.Interaction,الرابط:str):
    slug=الرابط.strip().split("kick.com/")[-1].split("/")[0].split("?")[0].lower().strip()
    if not slug:
        return await interaction.response.send_message("❌ رابط غلط، مثال: https://kick.com/id7o",ephemeral=True)
    # رد فوري عشان ما يعلق thinking
    await interaction.response.send_message(f"⏳ جاري فحص `{slug}`...",ephemeral=True)
    info=await get_kick_info(slug)
    if not info:
        return await interaction.followup.send(f"❌ ما لقيت `{slug}` - Kick ما رد، جرب مرة ثانية")
    embed=discord.Embed(description=f"{info['title']}",color=0x53FC18 if info['is_live'] else 0xED4245)
    embed.set_author(name=f"{'[LIVE] 🔴' if info['is_live'] else '[OFFLINE] ⚫️'} {info['username']}",icon_url=info["profile_pic"])
    if info["thumbnail"]: embed.set_image(url=info["thumbnail"])
    if info["category_thumb"]: embed.set_thumbnail(url=info["category_thumb"])
    if info["category"]: embed.set_footer(text=info["category"])
    status = f"🔴 لايف الحين" if info['is_live'] else "⚫️ اوفلاين"
    await interaction.followup.send(content=f"**{slug}** - {status}",embed=embed,view=KickView(slug))

@bot.tree.command(name="فحص_الان",description="ارسل كل اللي فاتحين الحين غصب في روم kick-streaming")
async def force_check(interaction:discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("❌ تحتاج صلاحية Manage Server",ephemeral=True)
    await interaction.response.send_message("⏳ افحص الحين...",ephemeral=True)
    sent=[]
    for slug in STREAMERS:
        info=await get_kick_info(slug)
        if info and info["is_live"]:
            ch=bot.get_channel(CHANNEL_ID)
            if not ch:
                for g in bot.guilds:
                    ch=g.get_channel(CHANNEL_ID)
                    if ch: break
            if ch:
                embed=discord.Embed(description=f"{info['title']}",color=0x53FC18)
                embed.set_author(name=f"{info['username']} LIVE!",icon_url=info["profile_pic"])
                if info["thumbnail"]: embed.set_image(url=info["thumbnail"])
                if info["category"]: embed.set_footer(text=f"{info['category']}")
                if info["category_thumb"]: embed.set_thumbnail(url=info["category_thumb"])
                try:
                    await ch.send(content=f"🟢 **{slug}** لايف!\n{info['title']}",embed=embed,view=KickView(slug))
                    sent.append(slug)
                    live_cache[slug]=True
                except Exception as e:
                    print(e)
    await interaction.followup.send(f"✅ تم ارسال {len(sent)} في <#{CHANNEL_ID}>: {', '.join(sent) if sent else 'ما فيه احد فاتح الحين'}",ephemeral=True)

app=Flask('')
@app.route('/')
def home(): return f"BOT OK | Channel {CHANNEL_ID} | Live cache: {live_cache} | Time: {__import__('datetime').datetime.now()}"
threading.Thread(target=lambda: app.run(host='0.0.0.0',port=8080)).start()
bot.run(TOKEN)
