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
    print(f"✅ BOT READY: {bot.user}")
    # فعل الامر /كلاش فورا
    try: await bot.tree.sync()
    except Exception as e: print(f"sync error {e}")
    check_kick.start()

async def get_kick_info(slug):
    headers = {"User-Agent":"Mozilla/5.0","Accept":"application/json"}
    try:
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"https://kick.com/api/v2/channels/{slug}",timeout=15) as r:
                if r.status==200:
                    data=await r.json()
                    ls=data.get("livestream")
                    last=data.get("last_broadcast") or {}
                    cat = (ls.get("categories")[0] if ls and ls.get("categories") else last.get("categories")[0] if last.get("categories") else {}) if True else {}
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
    print("--- CHECKING ---")
    for slug in STREAMERS:
        info = await get_kick_info(slug)
        if not info:
            print(f"{slug}: no info")
            continue
        print(f"{slug}: live={info['is_live']} cache={live_cache.get(slug)} title={info['title'][:20]}")
        was = live_cache.get(slug, False)
        # اذا لايف الحين وما كان لايف قبل = ارسل
        # وايضا اذا اول مرة والبوت توه اشتغل وهو لايف = ارسل مرة وحدة
        if info["is_live"] and not was:
            live_cache[slug]=True
            ch = bot.get_channel(CHANNEL_ID)
            if not ch:
                print(f"ERROR: channel {CHANNEL_ID} not found!")
                # جرب يجيبه من الكاش
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
                    print(f"SENT {slug} to {CHANNEL_ID}")
                except Exception as e:
                    print(f"send fail {slug}: {e}")
        elif not info["is_live"]:
            live_cache[slug]=False

@bot.tree.command(name="كلاش",description="تيست رابط الستريمر")
@app_commands.describe(الرابط="https://kick.com/id7o")
async def clash(interaction:discord.Interaction,الرابط:str):
    await interaction.response.defer()
    slug=Rابط.strip().split("kick.com/")[-1].split("/")[0].split("?")[0].lower().strip()
    info=await get_kick_info(slug)
    if not info: return await interaction.followup.send(f"❌ ما لقيت {slug}")
    embed=discord.Embed(description=f"{info['title']}",color=0x53FC18 if info['is_live'] else 0xED4245)
    embed.set_author(name=f"{'[LIVE] ' if info['is_live'] else '[OFFLINE] '}{info['username']}",icon_url=info["profile_pic"])
    if info["thumbnail"]: embed.set_image(url=info["thumbnail"])
    if info["category_thumb"]: embed.set_thumbnail(url=info["category_thumb"])
    if info["category"]: embed.set_footer(text=info["category"])
    status="🔴 لايف الحين - 22 watching زي الصورة" if info['is_live'] else "⚫️ اوفلاين"
    await interaction.followup.send(content=f"**{slug}** - {status}",embed=embed,view=KickView(slug))

# امر يجبر الارسال حتى لو كان لايف من زمان
@bot.tree.command(name="فحص_الان",description="افحص وارسل اللي فاتحين الحين غصب")
async def force_check(interaction:discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("ما عندك صلاحية",ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    sent=[]
    for slug in STREAMERS:
        info=await get_kick_info(slug)
        if info and info["is_live"]:
            ch=bot.get_channel(CHANNEL_ID)
            if ch:
                embed=discord.Embed(description=f"{info['title']}",color=0x53FC18)
                embed.set_author(name=f"{info['username']}",icon_url=info["profile_pic"])
                if info["thumbnail"]: embed.set_image(url=info["thumbnail"])
                if info["category_thumb"]: embed.set_thumbnail(url=info["category_thumb"])
                if info["category"]: embed.set_footer(text=info["category"])
                await ch.send(content=f"🟢 **{slug}** لايف!\n{info['title']}",embed=embed,view=KickView(slug))
                sent.append(slug)
    await interaction.followup.send(f"✅ ارسلت {len(sent)}: {', '.join(sent)} في <#{CHANNEL_ID}>",ephemeral=True)

app=Flask('')
@app.route('/')
def home(): return f"OK {CHANNEL_ID} - {live_cache}"
threading.Thread(target=lambda: app.run(host='0.0.0.0',port=8080)).start()
bot.run(TOKEN)
