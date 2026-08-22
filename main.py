import discord
from discord.ext import commands, tasks
import os, aiohttp, asyncio
from flask import Flask
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ROLE = 1537833274875838515 # بس هذا الرول يقدر يستخدم
ROOM_RT = 1537833593919901706
ROOM_MT = 1540466423854268537
ROLE_PING = 1538971924523253961

STREAMERS_RT = ["hook","seagull","drb7h","f1aisal","fhlwy","peerless","imonkey_d","abo8alyy","abo_khrbaa","id7o","s5b","okb8","taf86","aymnalsatam"]
STREAMERS_MT = ["firas","osamah","abokhaled_sa","abokyan","abdulrhman","majah92","brof2","tmnaa","7omah","sxb","abuswe7l"]
ALL = STREAMERS_RT + STREAMERS_MT

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
live = {}

async def get_kick(slug):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://kick.com/api/v2/channels/{slug}", timeout=8) as r:
                if r.status == 200:
                    d = await r.json()
                    ls = d.get("livestream")
                    return {"is_live": ls is not None, "title": (ls or {}).get("session_title") or ""}
    except: pass
    return {"is_live": False, "title": ""}

@tasks.loop(seconds=30)
async def checker():
    for slug in ALL:
        info = await get_kick(slug)
        was = live.get(slug, False)
        target = ROOM_RT if slug in STREAMERS_RT else ROOM_MT
        if info["is_live"] and not was:
            live[slug] = True
            ch = bot.get_channel(target)
            if not ch:
                for g in bot.guilds:
                    ch = g.get_channel(target)
                    if ch: break
            if ch:
                try:
                    await ch.send(f"<@&{ROLE_PING}> 🟢 **{slug}** فتح بث! https://kick.com/{slug}")
                except: pass
        elif not info["is_live"] and was:
            live[slug] = False

def is_owner():
    def predicate(ctx):
        if not ctx.guild: return False
        return any(r.id == OWNER_ROLE for r in ctx.author.roles)
    return commands.check(predicate)

@bot.event
async def on_ready():
    # 1. امسح كل اوامر السلاش نهائيا مرة وحدة
    try:
        await bot.http.bulk_overwrite_global_application_commands(bot.application_id, [])
        for g in bot.guilds:
            await bot.http.bulk_overwrite_guild_application_commands(bot.application_id, g.id, [])
        print("ALL SLASH DELETED - will disappear from / menu in ~10min")
    except Exception as e:
        print(f"delete error: {e}")

    # 2. امسح الكاش حق tree
    bot.tree.clear_commands(guild=None)
    for g in bot.guilds:
        bot.tree.clear_commands(guild=g)

    if not checker.is_running():
        checker.start()
    print(f"Ready {bot.user} - Only! commands for role {OWNER_ROLE}")

@bot.command(name="كلاش")
@is_owner()
async def clash_cmd(ctx, رابط: str = None):
    if not رابط:
        return await ctx.send("استخدم: `!كلاش https://kick.com/id7o`")
    slug = رابط.split("kick.com/")[-1].split("/")[0].split("?")[0].lower().strip()
    info = await get_kick(slug)
    await ctx.send(f"**{slug}**: {'🟢 لايف' if info['is_live'] else '⚫️ اوفلاين'}")

@bot.command(name="فحص_الان")
@is_owner()
async def check_cmd(ctx):
    await ctx.send("🔍 بفحص...")
    found = []
    for slug in ALL:
        info = await get_kick(slug)
        if info["is_live"]:
            found.append(slug)
            live[slug] = True
            target = ROOM_RT if slug in STREAMERS_RT else ROOM_MT
            ch = bot.get_channel(target) or next((g.get_channel(target) for g in bot.guilds if g.get_channel(target)), None)
            if ch:
                await ch.send(f"<@&{ROLE_PING}> 🟢 **{slug}** لايف https://kick.com/{slug}")
                await asyncio.sleep(0.5)
    if found:
        await ctx.send(f"✅ ارسلت {', '.join(found)}")
    else:
        await ctx.send("⚫️ مافي حد فاتح")

# لو واحد ما معه الرول كتب الامر - لا ترد ولا شي (يسكت)
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        return # اسكت - كأنه الامر مو موجود
    # باقي الاخطاء تجاهلها
    return

# Flask for hosting
app = Flask('')
@app.route('/')
def home(): return "Bot Running - No Slash Commands"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()

bot.run(TOKEN)
