import discord
from discord.ext import commands, tasks
import os, aiohttp
from flask import Flask
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ROLE = 1537833274875838515
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
live_messages = {}

class StreamView(discord.ui.View):
    def __init__(self, slug, is_live=True):
        super().__init__(timeout=None)
        url = f"https://kick.com/{slug}"
        label = "فتح البث" if is_live else "شاهد التسجيل"
        emoji = "🟢" if is_live else "🎥"
        self.add_item(discord.ui.Button(label=label, style=discord.ButtonStyle.link, url=url, emoji=emoji))

# هذا نفس كودك بس صلحت الـ API
async def get_kick(slug):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"https://kick.com/api/v2/channels/{slug}", timeout=10) as r:
                if r.status==200:
                    d=await r.json()
                    return {"is_live": d.get("livestream") is not None}
    except Exception as e:
        print(f"Error {slug}: {e}")
    return {"is_live": False}

@tasks.loop(seconds=30)
async def checker():
    for slug in ALL:
        info = await get_kick(slug)
        was = live.get(slug, False)
        target = ROOM_RT if slug in STREAMERS_RT else ROOM_MT

        ch = bot.get_channel(target)
        if not ch:
            for g in bot.guilds:
                ch=g.get_channel(target)
                if ch: break
        if not ch: continue

        if info["is_live"] and not was:
            live[slug]=True
            view = StreamView(slug, is_live=True)
            try:
                msg = await ch.send(f"<@&{ROLE_PING}> 🟢 **{slug}** فتح\nhttps://kick.com/{slug}", view=view)
                live_messages[slug] = {"id": msg.id, "ch": ch.id}
                print(f"SENT {slug} LIVE")
            except Exception as e:
                print(f"Send fail {slug}: {e}")

        elif not info["is_live"] and was:
            live[slug]=False
            data = live_messages.get(slug)
            if data:
                try:
                    old_ch = bot.get_channel(data["ch"]) or await bot.fetch_channel(data["ch"])
                    msg = await old_ch.fetch_message(data["id"])
                    view = StreamView(slug, is_live=False)
                    await msg.edit(content=f"🔴 **{slug}** انتهى البث - شاهد التسجيل\nhttps://kick.com/{slug}", view=view)
                    print(f"EDITED {slug} TO VOD")
                except: pass

@bot.event
async def on_ready():
    try:
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        for g in bot.guilds:
            bot.tree.clear_commands(guild=g)
            await bot.tree.sync(guild=g)
            await bot.http.bulk_overwrite_guild_application_commands(bot.application_id, g.id, [])
        await bot.http.bulk_overwrite_global_application_commands(bot.application_id, [])
    except: pass
    if not checker.is_running():
        checker.start()
    print(f"✅ READY {bot.user}")

def owner_only():
    def pred(ctx): return any(r.id == OWNER_ROLE for r in ctx.author.roles) if ctx.guild else False
    return commands.check(pred)

@bot.command(name="كلاش")
@owner_only()
async def clash(ctx, رابط: str = None):
    if not رابط: return
    slug=رابط.split("kick.com/")[-1].split("/")[0].lower()
    info=await get_kick(slug)
    await ctx.send(f"{slug} {'لايف' if info['is_live'] else 'اوفلاين'}", delete_after=10)
    try: await ctx.message.delete()
    except: pass

@bot.command(name="فحص_الان")
@owner_only()
async def f7s(ctx):
    for slug in ALL:
        info=await get_kick(slug)
        if info["is_live"] and not live.get(slug):
            live[slug]=True
            ch=bot.get_channel(ROOM_RT if slug in STREAMERS_RT else ROOM_MT)
            if ch:
                view = StreamView(slug, is_live=True)
                msg = await ch.send(f"<@&{ROLE_PING}> 🟢 **{slug}** فتح\nhttps://kick.com/{slug}", view=view)
                live_messages[slug] = {"id": msg.id, "ch": ch.id}
    try: await ctx.message.delete()
    except: pass

@bot.event
async def on_command_error(ctx, err):
    if isinstance(err, commands.CheckFailure):
        try: await ctx.message.delete()
        except: pass
        return

app=Flask('')
@app.route('/')
def h(): return "Kick Bot Fixed"
threading.Thread(target=lambda: app.run(host='0.0.0.0',port=8080),daemon=True).start()
bot.run(TOKEN)
