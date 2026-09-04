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

async def get_kick(slug):
    try:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        async with aiohttp.ClientSession(headers=headers) as s:
            async with s.get(f"https://kick.com/api/v2/channels/{slug}", timeout=10) as r:
                if r.status==200:
                    d=await r.json()
                    livestream = d.get("livestream")
                    if livestream:
                        # العنوان
                        title = livestream.get("session_title") or d.get("channel", {}).get("name") or "بث مباشر"
                        # صورة البث - اهم شي
                        thumb = None
                        th = livestream.get("thumbnail")
                        if isinstance(th, dict):
                            thumb = th.get("url") or th.get("src")
                        elif isinstance(th, str):
                            thumb = th
                        # اذا ما لقى صورة البث ياخذ البانر
                        if not thumb:
                            thumb = livestream.get("banner_image") or d.get("banner_image") or d.get("profile_pic")
                        
                        viewers = livestream.get("viewer_count", 0)
                        cats = livestream.get("categories") or []
                        category = cats[0].get("name") if cats and isinstance(cats[0], dict) else "Live"
                        
                        print(f"LIVE {slug}: {title} | {viewers} viewers")
                        return {"is_live": True, "title": title, "thumb": thumb, "viewers": viewers, "category": category}
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
        if not ch: 
            continue

        if info["is_live"] and not was:
            live[slug]=True
            view = StreamView(slug, is_live=True)
            
            embed = discord.Embed(
                title=f"🟢 {slug} فتح بث مباشر!",
                description=f"**{info.get('title','بث مباشر')}**\n📁 {info.get('category','Live')} | 👀 {info.get('viewers',0)} مشاهد",
                color=0x00FF00
            )
            if info.get('thumb'):
                embed.set_image(url=info.get('thumb'))
            embed.set_footer(text="Kick.com • بث مباشر الآن")
            
            try:
                msg = await ch.send(content=f"<@&{ROLE_PING}> 🟢 **{slug}** فتح\nhttps://kick.com/{slug}", embed=embed, view=view)
                live_messages[slug] = {"id": msg.id, "ch": ch.id}
                print(f"SENT {slug} WITH IMAGE")
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
                    
                    embed = discord.Embed(
                        title=f"🔴 {slug} أنهى البث",
                        description="البث انتهى - تقدر تشوف التسجيل الآن 👇",
                        color=0xFF0000
                    )
                    if msg.embeds and msg.embeds[0].image:
                        embed.set_image(url=msg.embeds[0].image.url)
                    embed.set_footer(text="Kick.com • التسجيل متاح")
                    
                    await msg.edit(content=f"🔴 **{slug}** انتهى البث - شاهد التسجيل\nhttps://kick.com/{slug}", embed=embed, view=view)
                    print(f"EDITED {slug} TO VOD")
                except Exception as e:
                    print(f"Edit fail {slug}: {e}")

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
        print("DELETED SLASH COMMANDS")
    except Exception as e:
        print(e)
    if not checker.is_running():
        checker.start()
    print(f"✅ READY {bot.user} - With Image Support")

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
    if info["is_live"]:
        embed = discord.Embed(title=f"🟢 {slug} لايف", description=info.get('title'), color=0x00FF00)
        if info.get('thumb'): embed.set_image(url=info.get('thumb'))
        await ctx.send(embed=embed, delete_after=30)
    else:
        await ctx.send(f"{slug} 🔴 اوفلاين", delete_after=10)
    try: await ctx.message.delete()
    except: pass

@bot.command(name="فحص_الان")
@owner_only()
async def f7s(ctx):
    await ctx.send("🔍 جاري الفحص مع الصور...", delete_after=5)
    for slug in ALL:
        info=await get_kick(slug)
        if info["is_live"] and not live.get(slug):
            live[slug]=True
            ch=bot.get_channel(ROOM_RT if slug in STREAMERS_RT else ROOM_MT)
            if ch:
                view = StreamView(slug, is_live=True)
                embed = discord.Embed(title=f"🟢 {slug} فتح بث مباشر!", description=f"{info.get('title')} | 👀 {info.get('viewers')} مشاهد", color=0x00FF00)
                if info.get('thumb'): embed.set_image(url=info.get('thumb'))
                msg = await ch.send(content=f"<@&{ROLE_PING}> 🟢 **{slug}** فتح\nhttps://kick.com/{slug}", embed=embed, view=view)
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
def h(): return "Kick Bot With Image + Button Online"
threading.Thread(target=lambda: app.run(host='0.0.0.0',port=8080),daemon=True).start()
bot.run(TOKEN)
