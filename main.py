import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, aiohttp, asyncio
from flask import Flask
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ROLE = 1537833274875838515
OWNER_ID = 1284167384021864458
ROOM_RT = 1537833593919901706
ROOM_MT = 1540466423854268537
ROLE_ID = 1538971924523253961
STREAMERS_RT = ["hook","seagull","drb7h","f1aisal","fhlwy","peerless","imonkey_d","abo8alyy","abo_khrbaa","id7o","s5b","okb8","taf86","aymnalsatam"]
STREAMERS_MT = ["firas","osamah","abokhaled_sa","abokyan","abdulrhman","majah92","brof2","tmnaa","7omah","sxb","abuswe7l"]
ALL = STREAMERS_RT + STREAMERS_MT

def only_owner(i: discord.Interaction):
    if i.user.id == OWNER_ID: return True
    m = i.guild.get_member(i.user.id) if i.guild else None
    return bool(m and any(r.id == OWNER_ROLE for r in m.roles))

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
live = {}

async def get_kick(slug):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://kick.com/api/v2/channels/{slug}", timeout=8) as r:
                if r.status==200:
                    d=await r.json()
                    return {"is_live": d.get("livestream") is not None}
    except: pass
    return {"is_live": False}

@tasks.loop(seconds=30)
async def checker():
    for slug in ALL:
        info = await get_kick(slug)
        was = live.get(slug, False)
        target = ROOM_RT if slug in STREAMERS_RT else ROOM_MT
        if info["is_live"] and not was:
            live[slug]=True
            ch=bot.get_channel(target) or next((g.get_channel(target) for g in bot.guilds if g.get_channel(target)), None)
            if ch:
                try: await ch.send(f"<@&{ROLE_ID}> 🟢 **{slug}** فتح https://kick.com/{slug}")
                except: pass
        elif not info["is_live"]:
            live[slug]=False

@bot.event
async def on_ready():
    print("START CLEAN")
    # 1. احذف كل الاوامر العالمية اللي سببت التكرار
    try:
        await bot.http.bulk_overwrite_global_application_commands(bot.application_id, [])
        print("Global deleted")
    except Exception as e:
        print(e)
    await asyncio.sleep(2)

    # 2. احذف اوامر السيرفر القديمة
    for g in bot.guilds:
        try:
            await bot.http.bulk_overwrite_guild_application_commands(bot.application_id, g.id, [])
            print(f"Cleared guild {g.id}")
        except: pass
    await asyncio.sleep(2)

    # 3. عرّف الاوامر من جديد
    @bot.tree.command(name="كلاش", description="فحص")
    @app_commands.describe(الرابط="kick.com/xxx")
    async def clash(interaction: discord.Interaction, الرابط: str):
        if not only_owner(interaction):
            return await interaction.response.send_message("❌ بس للاونر", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        slug=الرابط.split("kick.com/")[-1].split("/")[0].lower()
        info=await get_kick(slug)
        await interaction.followup.send(f"{slug} {'لايف' if info['is_live'] else 'اوفلاين'}", ephemeral=True)

    @bot.tree.command(name="فحص_الان", description="ارسل اللي فاتحين")
    async def f7s(interaction: discord.Interaction):
        if not only_owner(interaction):
            return await interaction.response.send_message("❌ بس للاونر", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("✅ تم", ephemeral=True)

    # 4. ثبتهم كـ guild commands فقط + اخفيهم
    for g in bot.guilds:
        try:
            await bot.tree.sync(guild=g)
            await asyncio.sleep(1)
            cmds = await bot.tree.fetch_commands(guild=g)
            for cmd in cmds:
                perms = [
                    {"id": g.id, "type": 1, "permission": False},
                    {"id": OWNER_ROLE, "type": 1, "permission": True},
                    {"id": OWNER_ID, "type": 2, "permission": True},
                ]
                await bot.http.edit_application_command_permissions(bot.application_id, g.id, cmd.id, perms)
                print(f"Hidden {cmd.name} -> only role {OWNER_ROLE}")
        except Exception as e:
            print(f"hide error {e}")

    if not checker.is_running():
        checker.start()
    print("DONE - now only owner role sees commands")

app = Flask('')
@app.route('/')
def h(): return "OK"
threading.Thread(target=lambda: app.run(host='0.0.0.0',port=8080),daemon=True).start()
bot.run(TOKEN)
