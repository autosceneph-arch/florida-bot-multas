import discord
from discord import app_commands
from discord.ext import commands, tasks
import sqlite3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

conn = sqlite3.connect('multas.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS multas (
    id INTEGER PRIMARY KEY, miembro_id INTEGER, miembro_nombre TEXT, oficial_id INTEGER,
    oficial_nombre TEXT, tipo TEXT, motivo TEXT, valor INTEGER, fecha_creacion TEXT,
    fecha_vencimiento TEXT, pagada INTEGER DEFAULT 0, id_multa TEXT
)''')

c.execute('''CREATE TABLE IF NOT EXISTS config (
    guild_id INTEGER PRIMARY KEY, rol_policia INTEGER, rol_staff INTEGER, rol_sancion INTEGER
)''')
conn.commit()

def tiene_permiso(interaction, nivel):
    c.execute("SELECT rol_policia, rol_staff FROM config WHERE guild_id=?", (interaction.guild_id,))
    roles = c.fetchone()
    if not roles: return False
    rp, rs = roles
    member = interaction.user
    if nivel == "staff" and rs and any(r.id == rs for r in member.roles): return True
    if nivel == "policia" and rp and any(r.id == rp for r in member.roles): return True
    return False

@tree.command(name="multa_configurar_roles", description="Configurar roles")
@app_commands.describe(rol_policia="Rol Policía", rol_staff="Rol Staff", rol_sancion="Rol Sanción")
async def configurar(interaction: discord.Interaction, rol_policia: discord.Role, rol_staff: discord.Role, rol_sancion: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Solo admins", ephemeral=True)
    c.execute("INSERT OR REPLACE INTO config VALUES (?,?,?,?)", 
              (interaction.guild_id, rol_policia.id, rol_staff.id, rol_sancion.id))
    conn.commit()
    await interaction.response.send_message("✅ Roles configurados", ephemeral=True)

@tree.command(name="multa_crear", description="Crear multa")
@app_commands.describe(miembro="Miembro", tipo="Tipo", motivo="Motivo", valor="Valor")
async def crear(interaction: discord.Interaction, miembro: discord.Member, tipo: str, motivo: str, valor: int):
    if not tiene_permiso(interaction, "policia"):
        return await interaction.response.send_message("No tienes permiso", ephemeral=True)
    
    await interaction.response.defer()
    now = datetime.now()
    venc = now + timedelta(days=3)
    idm = f"#{now.strftime('%y%m%d%H%M')}"

    c.execute("INSERT INTO multas VALUES (NULL,?,?,?,?,?,?,?,?,?,0,?)",
              (miembro.id, str(miembro), interaction.user.id, str(interaction.user),
               tipo, motivo, valor, now.isoformat(), venc.isoformat(), idm))
    conn.commit()

    embed = discord.Embed(title="📋 REGISTRO DE MULTA", color=0xff0000)
    embed.add_field(name="Ciudadano", value=miembro.mention, inline=False)
    embed.add_field(name="Oficial", value=interaction.user.mention, inline=False)
    embed.add_field(name="Tipo", value=tipo, inline=True)
    embed.add_field(name="Motivo", value=motivo, inline=True)
    embed.add_field(name="Valor", value=f"R$ {valor:,}", inline=False)
    embed.add_field(name="Vence", value=venc.strftime("%d/%m/%Y"), inline=False)
    embed.add_field(name="ID", value=idm, inline=False)

    await interaction.followup.send(embed=embed)
    try: await miembro.send(embed=embed)
    except: pass

@tree.command(name="multa_lista", description="Ver multas pendientes")
async def lista(interaction: discord.Interaction):
    c.execute("SELECT * FROM multas WHERE miembro_id=? AND pagada=0", (interaction.user.id,))
    multas = c.fetchall()
    if not multas:
        return await interaction.response.send_message("No tienes multas pendientes.", ephemeral=True)
    embed = discord.Embed(title="Tus Multas", color=0xffaa00)
    for m in multas:
        embed.add_field(name=f"ID {m[11]} - R$ {m[7]}", value=f"{m[5]}\nVence: {m[9][:10]}", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot {bot.user} en línea!")

bot.run(os.getenv("TOKEN"))
