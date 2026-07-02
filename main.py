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

# Base de datos
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

# ==================== COMANDO CREAR MULTA ====================

@tree.command(name="multa_crear", description="Crear una multa oficial")
@app_commands.describe(
    miembro="Miembro a multar",
    tipo="Tipo de multa",
    motivo="Motivo de la multa",
    valor="Valor de la multa"
)
@app_commands.choices(tipo=[
    app_commands.Choice(name="Presencial", value="Presencial"),
    app_commands.Choice(name="Digital", value="Digital"),
    app_commands.Choice(name="Warn", value="Warn")
])
async def multa_crear(
    interaction: discord.Interaction,
    miembro: discord.Member,
    tipo: app_commands.Choice[str],
    motivo: str,
    valor: int
):
    if not tiene_permiso(interaction, "policia"):
        return await interaction.response.send_message("❌ No tienes permiso para crear multas.", ephemeral=True)

    await interaction.response.defer()

    now = datetime.now()
    vencimiento = now + timedelta(days=3)
    id_multa = f"#{now.strftime('%y%m%d%H%M')}"

    c.execute("INSERT INTO multas VALUES (NULL,?,?,?,?,?,?,?,?,?,0,?)",
              (miembro.id, str(miembro), interaction.user.id, str(interaction.user),
               tipo.value, motivo, valor, now.isoformat(), vencimiento.isoformat(), id_multa))
    conn.commit()

    embed = discord.Embed(title="🔴 REGISTRO DE MULTA", color
