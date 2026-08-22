import discord
from discord.ext import commands, tasks
from discord import app_commands
import os, aiohttp, asyncio
from flask import Flask
import threading

TOKEN = os.getenv("DISCORD_TOKEN")
ROOM_RT = 1537833593919901706
ROOM_MT = 1540466423854268537
ROLE_ID = 1538971924523253961
OWNER_ROLE_ID = 1537833274875838515
OWNER_ID = 1284167384021864458

STREAMERS_RT = ["hook","seagull","drb7h","f1aisal","fhlwy","peerless","imonkey_d","abo8alyy","abo_khrbaa","id7o","s5b","okb8","taf86","aymnalsatam"]
STREAMERS_MT = ["firas","osamah","abokhaled_sa","abokyan","abdulrhman","majah92","brof2","tmnaa","7omah","sxb","abuswe7l"]
ALL_STREAMERS = STREAMERS_RT + STREAMERS_MT

def only_owner(interaction: discord.Interaction):
    if interaction.user.id == OWNER_ID:
        return True
    if interaction.guild:
        member = interaction.guild.get_member(interaction.user.id)
        if member and any(r.id == OWNER_ROLE_ID for r in member.roles):
            return True
    return False

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents)
live_cache = {}

async def get_kick_info(slug):
    headers = {"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":f"https://kick.com/{slug}"}
    for url in [f"https://kick.com/api/v2/channels/{slug}", f"https://kick.com/api/v1/channels/{slug}"]:
        try:
            async with aiohttp.ClientSession(headers=headers) as s:
                async with s.get(url, timeout=8) as r:
                    if r.status==200:
                        data=await r.json()
                        ls=data.get("livestream")
                        return {"is_live": ls is not None, "title": (ls or {}).get("session_title") or "No Title", "thumbnail": (ls or {}).get("thumbnail",{}).get("url") if isinstance((ls or {}).get("thumbnail"),dict) else (ls or {}).get("thumbnail")}
        except: pass
    return None

class KickView(discord.ui.View):
    def __init__(self, slug):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label=f"Kick.com/{slug}", url=f"https://kick.com/{slug}", emoji="🔗"))

@tasks.loop(seconds=30)
async def check_kick():
    for slug in ALL_STREAMERS:
        info=await get_kick_info(slug)
        if not info: continue
        was=live_cache.get(slug, False)
        target=ROOM_RT if slug in STREAMERS_RT else ROOM_MT
        if info["is_live"] and not was:
            live_cache[slug]=True
            ch=bot.get_channel(target)
            if not ch:
                for g in bot.guilds:
                    ch=g.get_channel(target)
                    if ch: break
            if ch:
                e=discord.Embed(description=info['title'], color=0x53FC18)
                e.set_author(name=f"{slug} LIVE!")
                if info["thumbnail"]: e.set_image(url=info["thumbnail"])
                try: await ch.send(content=f"<@&{ROLE_ID}> 🟢 **{slug} فتح بث!**", embed=e, view=KickView(slug))
                except: pass
        elif not info["is_live"]:
            live_cache[slug]=False

@bot.event
async def on_ready():
    print(f"READY {bot.user} in {len(bot.guilds)} guilds")
    # 1. نسوي sync للاوامر كـ guild commands عشان نقدر نخفيها
    for guild in bot.guilds:
        try:
            # انسخ الاوامر كـ guild commands
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"synced to {guild.name}")
            
            # 2. اخفي الاوامر عن الكل الا رول الاونر
            await asyncio.sleep(2)
            cmds = await bot.tree.fetch_commands(guild=guild)
            for cmd in cmds:
                if cmd.name in ["كلاش", "فحص_الان"]:
                    # الصلاحيات: @everyone ممنوع، الاونر مسموح
                    perms = [
                        app_commands.Permission(id=guild.id, type=app_commands.PermissionType.role, permission=False),
                        app_commands.Permission(id=OWNER_ROLE_ID, type=app_commands.PermissionType.role, permission=True),
                    ]
                    # اضافة الاونر كـ user كمان للضمان
                    try:
                        perms.append(app_commands.Permission(id=OWNER_ID, type=app_commands.PermissionType.user, permission=True))
                    except: pass
                    
                    try:
                        await guild.bulk_edit_command_permissions({cmd.id: perms})
                        print(f"Hidden {cmd.name} in {guild.name} - only owner role can see")
                    except Exception as e:
                        print(f"perm error {cmd.name}: {e}")
                        # محاولة ثانية بالطريقة القديمة
                        try:
                            await bot.http.edit_application_command_permissions(bot.application_id, guild.id, cmd.id, [{"id": guild.id, "type": 1, "permission": False}, {"id": OWNER_ROLE_ID, "type": 1, "permission": True}])
                        except Exception as e2:
                            print(f"second try fail {e2}")

        except Exception as e:
            print(f"guild error {e}")

    if not check_kick.is_running():
        check_kick.start()

@bot.tree.command(name="كلاش", description="فحص")
@app_commands.describe(الرابط="https://kick.com/id7o")
@app_commands.check(only_owner)
async def clash(interaction: discord.Interaction, الرابط: str):
    await interaction.response.defer(ephemeral=True)
    slug=الرابط.split("kick.com/")[-1].split("/")[0].lower().strip()
    info=await get_kick_info(slug)
    if not info: return await interaction.followup.send("❌ Kick حاجب", ephemeral=True)
    e=discord.Embed(description=info['title'], color=0x53FC18 if info['is_live'] else 0xED4245)
    if info["thumbnail"]: e.set_image(url=info["thumbnail"])
    await interaction.followup.send(f"**{slug}** - {'🔴 لايف' if info['is_live'] else '⚫️ اوفلاين'}", embed=e, view=KickView(slug), ephemeral=True)

@bot.tree.command(name="فحص_الان", description="ارسل اللي فاتحين غصب")
@app_commands.check(only_owner)
async def force_check(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    sent=[]
    for slug in ALL_STREAMERS:
        info=await get_kick_info(slug)
        if info and info['is_live']:
            target=ROOM_RT if slug in STREAMERS_RT else ROOM_MT
            ch=bot.get_channel(target) or next((g.get_channel(target) for g in bot.guilds if g.get_channel(target)), None)
            if ch:
                e=discord.Embed(description=info['title'], color=0x53FC18)
                e.set_author(name=f"{slug} LIVE!")
                if info["thumbnail"]: e.set_image(url=info["thumbnail"])
                await ch.send(content=f"<@&{ROLE_ID}> 🟢 **{slug}** لايف!", embed=e, view=KickView(slug))
                sent.append(slug)
                live_cache[slug]=True
                await asyncio.sleep(1)
    await interaction.followup.send(f"✅ {', '.join(sent) or 'مافي احد فاتح'}", ephemeral=True)

@bot.tree.error
async def on_app_command_error(i,e):
    if isinstance(e, app_commands.CheckFailure):
        try: await i.response.send_message("❌ بس للاونر", ephemeral=True)
        except:
            try: await i.followup.send("❌ بس للاونر", ephemeral=True)
            except: pass

app = Flask('')
@app.route('/')
def home(): return "OK"
threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080), daemon=True).start()
bot.run(TOKEN)
