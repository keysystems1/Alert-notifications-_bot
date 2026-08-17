import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, json, aiohttp
from flask import Flask
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "kick_data.json"
CHANNEL_ID = 1537833593919901706 # روم البثوث الثابت

STREAMERS = [
    "hook", "seagull", "drb7h", "f1aisal", "fhlwy", "peerless",
    "imonkey_d", "abo8alyy", "abo_khrbaa", "id7o", "s5b", "okb8", "taf86", "firas"
]

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}
def save_data(d):
    with open(DATA_FILE, "w") as f: json.dump(d, f, indent=2)

kick_data = load_data()
live_cache = {}

@bot.event
async def on_ready():
    await bot.tree.sync()
    check_kick.start()
    print(f"✅ ONLINE - Channel: {CHANNEL_ID}")

async def get_kick_info(slug):
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            data = None
            async with session.get(f"https://kick.com/api/v2/channels/{slug}", timeout=15) as r:
                if r.status == 200: data = await r.json()
            if not data:
                async with session.get(f"https://kick.com/api/v1/channels/{slug}", timeout=15) as r2:
                    if r2.status == 200:
                        raw = await r2.json()
                        data = {"slug": raw.get("slug") or slug, "user": raw.get("user"), "livestream": raw.get("livestream"), "last_broadcast": raw.get("last_broadcast")}
            if not data: return None
            livestream = data.get("livestream")
            last = data.get("last_broadcast") or {}
            cat_name = cat_thumb = None
            if livestream and livestream.get("categories"):
                cat_name = livestream["categories"][0].get("name")
                cat_thumb = livestream["categories"][0].get("thumbnail")
            elif last.get("categories"):
                cat_name = last["categories"][0].get("name")
                cat_thumb = last["categories"][0].get("thumbnail")
            thumb = None
            if livestream:
                t = livestream.get("thumbnail")
                thumb = t.get("url") if isinstance(t, dict) else t
            if not thumb and last:
                t = last.get("thumbnail")
                thumb = t.get("url") if isinstance(t, dict) else t
            title = (livestream.get("session_title") if livestream else "") or (last.get("session_title") or "")
            return {"username": data.get("slug") or slug, "profile_pic": (data.get("user") or {}).get("profile_pic"), "is_live": livestream is not None, "title": title, "category": cat_name, "category_thumb": cat_thumb, "thumbnail": thumb}
    except: return None

class KickView(discord.ui.View):
    def __init__(self, slug):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=f"Kick.com/{slug}", url=f"https://kick.com/{slug}", emoji="🔗"))
        self.add_item(discord.ui.Button(label="Watch VOD", url=f"https://kick.com/{slug}/videos", emoji="🔄"))

@tasks.loop(seconds=60)
async def check_kick():
    for slug in STREAMERS:
        info = await get_kick_info(slug)
        if not info: continue
        was_live = live_cache.get(slug, False)
        if info["is_live"] and not was_live:
            live_cache[slug] = True
            # يرسل في الروم الثابت 1537833593919901706
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                embed = discord.Embed(description=f"{info['title']}", color=0x0e0e10)
                embed.set_author(name=f"{info['username']} is LIVE!", icon_url=info["profile_pic"])
                if info["thumbnail"]: embed.set_image(url=info["thumbnail"])
                if info["category_thumb"]: embed.set_thumbnail(url=info["category_thumb"])
                if info["category"]: embed.set_footer(text=f"{info['category']}")
                try: await channel.send(content=f"🟢 {info['username']} فتح بث!", embed=embed, view=KickView(slug))
                except Exception as e: print(f"send fail {e}")
            # ويرسل ايضا في الرومات المحفوظة
            if slug in kick_data:
                for alert in kick_data[slug].get("alerts", []):
                    if alert["channel_id"] == CHANNEL_ID: continue
                    guild = bot.get_guild(alert["guild_id"])
                    if not guild: continue
                    ch = guild.get_channel(alert["channel_id"])
                    if not ch: continue
                    role_mention = ""
                    if alert.get("role_id"):
                        role = guild.get_role(alert["role_id"])
                        if role: role_mention = role.mention
                    content = f"🟢 {role_mention}" if role_mention else ""
                    embed = discord.Embed(description=f"{info['title']}", color=0x0e0e10)
                    embed.set_author(name=f"{info['username']}", icon_url=info["profile_pic"])
                    if info["thumbnail"]: embed.set_image(url=info["thumbnail"])
                    if info["category_thumb"]: embed.set_thumbnail(url=info["category_thumb"])
                    if info["category"]: embed.set_footer(text=f"{info['category']}")
                    try: await ch.send(content=content, embed=embed, view=KickView(slug))
                    except: pass
        elif not info["is_live"] and was_live:
            live_cache[slug] = False

@bot.tree.command(name="كلاش", description="تيست - حط رابط الستريمر")
@app_commands.describe(الرابط="مثلا https://kick.com/firas")
async def clash(interaction: discord.Interaction, الرابط: str):
    await interaction.response.defer()
    slug = الرابط.strip().split("kick.com/")[-1].split("/")[0].split("?")[0].lower().strip()
    if not slug: return await interaction.followup.send("❌ رابط غلط")
    info = await get_kick_info(slug)
    if not info: return await interaction.followup.send(f"❌ ما لقيت {slug}")
    embed = discord.Embed(description=f"{info['title']}", color=0x53FC18 if info['is_live'] else 0xED4245)
    embed.set_author(name=f"{'[LIVE] ' if info['is_live'] else '[OFFLINE] '}{info['username']}", icon_url=info["profile_pic"])
    if info["thumbnail"]: embed.set_image(url=info["thumbnail"])
    if info["category_thumb"]: embed.set_thumbnail(url=info["category_thumb"])
    if info["category"]: embed.set_footer(text=f"{info['category']}")
    status = "🔴 لايف الحين" if info['is_live'] else "⚫️ اوفلاين"
    await interaction.followup.send(content=f"**{slug}** - {status}", embed=embed, view=KickView(slug))

@bot.tree.command(name="اضافة_الكل", description="اضافة كل الـ 14")
@app_commands.describe(روم_التنبيه="الروم", رتبة_المنشن="رتبة")
async def add_all(interaction: discord.Interaction, روم_التنبيه: discord.TextChannel, رتبة_المنشن: discord.Role = None):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("❌ ما عندك صلاحية", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    for slug in STREAMERS:
        if slug not in kick_data: kick_data[slug] = {"alerts": []}
        if not any(a["guild_id"]==interaction.guild.id and a["channel_id"]==روم_التنبيه.id for a in kick_data[slug]["alerts"]):
            kick_data[slug]["alerts"].append({"guild_id": interaction.guild.id, "channel_id": روم_التنبيه.id, "role_id": رتبة_المنشن.id if رتبة_المنشن else None})
    save_data(kick_data)
    await interaction.followup.send(f"✅ تم اضافة {len(STREAMERS)} في {روم_التنبيه.mention}\nوالروم الثابت هو <#{CHANNEL_ID}>", ephemeral=True)

@bot.tree.command(name="قائمة_كيك", description="شوف التنبيهات")
async def list_kick(interaction: discord.Interaction):
    await interaction.response.send_message(f"الروم الثابت: <#{CHANNEL_ID}> `({CHANNEL_ID})`\nالستريمرز: {', '.join(STREAMERS)}", ephemeral=True)

app = Flask('')
@app.route('/')
def home(): return f"Kick Bot - Channel {CHANNEL_ID}"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080)).start()
bot.run(TOKEN)
