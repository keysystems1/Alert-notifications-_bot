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
live_messages = {}  # slug -> {message_id, channel_id}

# زر فتح البث / شاهد التسجيل
class StreamView(discord.ui.View):
    def __init__(self, slug, is_live=True):
        super().__init__(timeout=None)
        url = f"https://kick.com/{slug}"
        if is_live:
            btn = discord.ui.Button(label="فتح البث", style=discord.ButtonStyle.link, url=url, emoji="🟢")
        else:
            btn = discord.ui.Button(label="شاهد التسجيل", style=discord.ButtonStyle.link, url=url, emoji="🎥")
        self.add_item(btn)

async def get_kick(slug):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://kick.com/api/v2/channels/{slug}", timeout=8) as r:
                if r.status==200:
                    d=await r.json()
                    livestream = d.get("livestream")
                    is_live = livestream is not None
                    title = livestream.get("session_title") if livestream else None
                    thumb = d.get("banner_image") or d.get("profile_pic")
                    return {"is_live": is_live, "title": title, "thumb": thumb}
    except Exception as e:
        print(f"Error {slug}: {e}")
    return {"is_live": False, "title": None, "thumb": None}

def get_target_room(slug):
    return ROOM_RT if slug in STREAMERS_RT else ROOM_MT

@tasks.loop(seconds=30)
async def checker():
    for slug in ALL:
        info = await get_kick(slug)
        was_live = live.get(slug, False)
        target = get_target_room(slug)
        
        # لقى روم
        ch = bot.get_channel(target)
        if not ch:
            for g in bot.guilds:
                ch = g.get_channel(target)
                if ch: break
        if not ch: continue

        # فتح بث جديد
        if info["is_live"] and not was_live:
            live[slug] = True
            embed = discord.Embed(
                title=f"🟢 {slug} فتح بث مباشر!",
                description=f"**{info['title'] or 'بث مباشر الآن'}**\n\nاضغط الزر تحت عشان تفتح البث 👇",
                color=0x00FF00
            )
            if info['thumb']:
                embed.set_thumbnail(url=info['thumb'])
            embed.set_footer(text="Kick.com • بث مباشر")
            
            view = StreamView(slug, is_live=True)
            try:
                msg = await ch.send(content=f"<@&{ROLE_PING}> 🟢 **{slug}** فتح لايف!", embed=embed, view=view)
                live_messages[slug] = {"message_id": msg.id, "channel_id": ch.id}
                print(f"LIVE {slug} -> {msg.id}")
            except Exception as e:
                print(f"Send error {slug}: {e}")

        # انتهى البث - عدل الرسالة ل "شاهد التسجيل"
        elif not info["is_live"] and was_live:
            live[slug] = False
            data = live_messages.get(slug)
            if data:
                try:
                    old_ch = bot.get_channel(data["channel_id"]) or await bot.fetch_channel(data["channel_id"])
                    msg = await old_ch.fetch_message(data["message_id"])
                    
                    embed = discord.Embed(
                        title=f"🔴 {slug} أنهى البث",
                        description=f"البث انتهى - تقدر تشوف التسجيل الآن 👇",
                        color=0xFF0000
                    )
                    if info['thumb']:
                        embed.set_thumbnail(url=info['thumb'])
                    embed.set_footer(text="Kick.com • التسجيل متاح")
                    
                    view = StreamView(slug, is_live=False)
                    await msg.edit(content=f"🔴 **{slug}** البث انتهى", embed=embed, view=view)
                    print(f"VOD {slug} -> edited")
                except Exception as e:
                    print(f"Edit error {slug}: {e}")
            # اذا ما لقينا الرسالة القديمة، لا ترسل شي جديد

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
        print("DELETED SLASH COMMANDS FOREVER")
    except Exception as e:
        print(e)
    if not checker.is_running():
        checker.start()
    print(f"✅ Kick Bot Ready - {bot.user}")

def owner_only():
    def pred(ctx):
        return any(r.id == OWNER_ROLE for r in ctx.author.roles) if ctx.guild else False
    return commands.check(pred)

@bot.command(name="كلاش")
@owner_only()
async def clash(ctx, رابط: str = None):
    if not رابط: return
    slug=رابط.split("kick.com/")[-1].split("/")[0].lower()
    info=await get_kick(slug)
    await ctx.send(f"{slug} {'🟢 لايف الآن' if info['is_live'] else '🔴 اوفلاين'}", delete_after=10)
    try: await ctx.message.delete()
    except: pass

@bot.command(name="فحص_الان")
@owner_only()
async def f7s(ctx):
    await ctx.send("🔍 جاري فحص كل الستريمرز...", delete_after=5)
    for slug in ALL:
        info=await get_kick(slug)
        if info["is_live"] and not live.get(slug):
            live[slug]=True
            ch=bot.get_channel(get_target_room(slug))
            if ch:
                embed = discord.Embed(title=f"🟢 {slug} فتح بث مباشر!", description=info['title'] or "بث مباشر الآن", color=0x00FF00)
                view = StreamView(slug, is_live=True)
                msg = await ch.send(content=f"<@&{ROLE_PING}> 🟢 **{slug}**", embed=embed, view=view)
                live_messages[slug] = {"message_id": msg.id, "channel_id": ch.id}
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
def h(): return "Kick Bot With Buttons Online"
threading.Thread(target=lambda: app.run(host='0.0.0.0',port=8080),daemon=True).start()
bot.run(TOKEN)
