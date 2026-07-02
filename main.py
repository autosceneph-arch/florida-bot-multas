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

# ==================== COMANDO CREAR MULTA (ACTUALIZADO) ====================

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

    embed = discord.Embed(title="🔴 REGISTRO DE MULTA", color=0xFF69B4)
    embed.description = "Se ha generado una multa oficial hacia el ciudadano mencionado.\nRevise la información y proceda con el pago."

    embed.add_field(name="👤 DATOS DEL CIUDADANO", value=f"**Ciudadano:** {miembro.mention}\n**ID:** `{miembro.id}`", inline=False)
    embed.add_field(name="👮 QUIEN LA PONE", value=f"**Oficial responsable:** {interaction.user.mention}\n**ID del oficial:** `{interaction.user.id}`", inline=False)
    embed.add_field(name="🔴 TIPO DE MULTA", value=tipo.value, inline=True)
    embed.add_field(name="📋 DETALLES DE LA MULTA", value=f"**Monto total:** $ {valor:,}\n**Motivo:** {motivo}\n**ID de multa:** {id_multa}", inline=False)
    
    embed.add_field(name="⏰ INFORMACIÓN IMPORTANTE", 
                    value="El ciudadano dispone de un plazo máximo de **3 días** para pagar la multa.\n"
                          "Si no realiza el pago, recibirá advertencias y luego será sancionado.", inline=False)

    # Nueva sección de pago
    embed.add_field(name="💰 CÓMO PAGAR UNA MULTA", 
                    value="Dirígete al canal de **Economía** y usa el comando:\n"
                          "`!pay @banco_flrp <cantidad>`\n\n"
                          "Después de pagar, **menciona al oficial** para que retire la multa.\n"
                          "Se recomienda avisarle **una vez por día**. Si no la retira en 2 días, contacta a soporte abriendo un ticket.", inline=False)
    
    embed.set_footer(text="FLRP • Sistema oficial de sanciones")
    embed.timestamp = now

    await interaction.followup.send(embed=embed)
    try:
        await miembro.send(embed=embed)
    except:
        pass

# ==================== COMANDO PAGAR ====================

@tree.command(name="multa_pagar", description="Marcar multa como pagada (Policía/Staff)")
@app_commands.describe(id_multa="ID de la multa pagada")
async def multa_pagar(interaction: discord.Interaction, id_multa: str):
    if not tiene_permiso(interaction, "policia"):
        return await interaction.response.send_message("❌ Solo Policía o Staff pueden marcar multas como pagadas.", ephemeral=True)

    c.execute("SELECT miembro_nombre, valor FROM multas WHERE id_multa=?", (id_multa,))
    multa = c.fetchone()

    if not multa:
        return await interaction.response.send_message(f"❌ No se encontró la multa con ID `{id_multa}`.", ephemeral=True)

    c.execute("DELETE FROM multas WHERE id_multa=?", (id_multa,))
    conn.commit()

    embed = discord.Embed(
        title="✅ MULTA PAGADA",
        description=f"La multa **{id_multa}** ha sido marcada como pagada.",
        color=0x00FF00
    )
    embed.add_field(name="Ciudadano", value=multa[0], inline=True)
    embed.add_field(name="Monto Pagado", value=f"$ {multa[1]:,}", inline=True)
    embed.add_field(name="Estado", value="**Al día con FLRP** ✅", inline=False)
    embed.set_footer(text="FLRP • Sistema oficial de sanciones")
    embed.timestamp = datetime.now()

    await interaction.response.send_message(embed=embed)

# ==================== COMANDOS ANTERIORES (sin cambios) ====================

@tree.command(name="multa_eliminar", description="Eliminar una multa (Solo Staff)")
@app_commands.describe(id_multa="ID de la multa a eliminar")
async def multa_eliminar(interaction: discord.Interaction, id_multa: str):
    if not tiene_permiso(interaction, "staff"):
        return await interaction.response.send_message("❌ Solo el Staff puede eliminar multas.", ephemeral=True)

    c.execute("DELETE FROM multas WHERE id_multa=?", (id_multa,))
    if c.rowcount > 0:
        conn.commit()
        embed = discord.Embed(title="✅ Multa Eliminada", description=f"La multa **{id_multa}** ha sido eliminada correctamente.", color=0x00FF00)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(f"❌ No se encontró la multa con ID `{id_multa}`.", ephemeral=True)

@tree.command(name="multa_lista", description="Ver multas pendientes de un usuario")
@app_commands.describe(miembro="Usuario a consultar (solo policías/staff)")
async def multa_lista(interaction: discord.Interaction, miembro: discord.Member = None):
    target = miembro or interaction.user

    if target != interaction.user and not tiene_permiso(interaction, "policia"):
        return await interaction.response.send_message("❌ Solo Policía o Staff pueden ver las multas de otros usuarios.", ephemeral=True)

    c.execute("SELECT * FROM multas WHERE miembro_id=? AND pagada=0", (target.id,))
    multas = c.fetchall()

    if not multas:
        return await interaction.response.send_message(f"✅ {target.mention} no tiene multas pendientes.", ephemeral=True)

    embed = discord.Embed(title=f"📋 Multas Pendientes - {target.display_name}", color=0xFF69B4)
    for m in multas:
        embed.add_field(
            name=f"ID: {m[11]} - $ {m[7]:,}",
            value=f"**Motivo:** {m[5]}\n**Tipo:** {m[5]}\n**Vence:** {m[9][:10]}",
            inline=False
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="multa_configurar_roles", description="Configurar roles")
@app_commands.describe(rol_policia="Rol Policía", rol_staff="Rol Staff", rol_sancion="Rol Sanción")
async def configurar_roles(interaction: discord.Interaction, rol_policia: discord.Role, rol_staff: discord.Role, rol_sancion: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("Solo administradores.", ephemeral=True)
    c.execute("INSERT OR REPLACE INTO config VALUES (?,?,?,?)", 
              (interaction.guild_id, rol_policia.id, rol_staff.id, rol_sancion.id))
    conn.commit()
    await interaction.response.send_message("✅ Roles configurados correctamente.", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ {bot.user} está en línea!")

bot.run(os.getenv("TOKEN"))
