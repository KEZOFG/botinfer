#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOT DE COMUNIDAD TELEGRAM - VERSIÓN COMPLETA
Comandos: /genkey, /redeem, /ban, /unban, /mute, /unmute, /refe, /staff, /id, /plan
"""

import os
import sqlite3
import secrets
import string
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from telegram.constants import ChatMemberStatus
from telegram.error import TelegramError

# ==================== CONFIGURACIÓN - EDITAR ESTO ====================
TOKEN = "8926218329:AAFh6Vy4UYHPfi_eWz-BR2GnMYtjuZWLkGY"  # Obtener de @BotFather

# IDs de los grupos (usar /id en cada grupo para obtenerlos)
GRUPO_VIP_ID = -1004493468867     # Reemplazar con ID real del grupo VIP
GRUPO_VENTAS_ID = -1001234567891   # Reemplazar con ID real del grupo de ventas
GRUPO_REFES_ID = -1001234567892    # Reemplazar con ID real del grupo de referencias

# IDs de administradores del bot (puedes agregar varios separados por coma)
ADMIN_IDS = [8886805386,6953415010,8000362074]  # Ejemplo: [123456789, 987654321]

# STAFF - Configurar aquí los miembros del staff
STAFF_CONFIG = [
    {"user_id": 123456789, "username": "admin1", "role": "👑 Fundador", "display_name": "Nombre Admin"},
    # Agregar más: {"user_id": 987654321, "username": "admin2", "role": "⭐ Moderador", "display_name": "Otro Admin"},
]

DB_FILE = "bot_comunidad.db"

# ==================== BASE DE DATOS ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Tabla de keys
    c.execute('''CREATE TABLE IF NOT EXISTS keys (
        key TEXT PRIMARY KEY,
        created_by INTEGER,
        created_at TIMESTAMP,
        duration_days INTEGER DEFAULT 30,
        redeemed_by INTEGER,
        redeemed_at TIMESTAMP,
        redeemed INTEGER DEFAULT 0
    )''')
    
    # Tabla de usuarios/planes
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        plan_start TIMESTAMP,
        plan_end TIMESTAMP,
        is_active INTEGER DEFAULT 0,
        redeemed_key TEXT
    )''')
    
    # Tabla de staff
    c.execute('''CREATE TABLE IF NOT EXISTS staff (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        role TEXT,
        display_name TEXT
    )''')
    
    # Tabla de usuarios baneados
    c.execute('''CREATE TABLE IF NOT EXISTS banned_users (
        user_id INTEGER PRIMARY KEY,
        banned_at TIMESTAMP,
        reason TEXT
    )''')
    
    # Tabla de usuarios muteados
    c.execute('''CREATE TABLE IF NOT EXISTS muted_users (
        user_id INTEGER PRIMARY KEY,
        muted_at TIMESTAMP,
        expires_at TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()

def get_db():
    return sqlite3.connect(DB_FILE)

def init_staff():
    """Inicializa el staff desde la configuración"""
    conn = get_db()
    c = conn.cursor()
    for member in STAFF_CONFIG:
        c.execute('''INSERT OR REPLACE INTO staff (user_id, username, role, display_name)
                     VALUES (?, ?, ?, ?)''', 
                  (member["user_id"], member["username"], member["role"], member["display_name"]))
    conn.commit()
    conn.close()

# ==================== FUNCIONES AUXILIARES ====================
def generate_key():
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(16))

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    try:
        member = context.bot.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except:
        return False

async def is_admin_or_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    return is_admin(user_id) or is_group_admin(update, context)

def get_staff_list():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT display_name, username, role FROM staff')
    staff = c.fetchall()
    conn.close()
    return staff

def check_and_update_plans(context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    now = datetime.now()
    
    c.execute('''SELECT user_id FROM users WHERE is_active = 1 AND plan_end < ?''', (now,))
    expired_users = c.fetchall()
    
    for (user_id,) in expired_users:
        try:
            context.bot.ban_chat_member(GRUPO_VIP_ID, user_id)
            context.bot.unban_chat_member(GRUPO_VIP_ID, user_id)
        except:
            pass
        c.execute('UPDATE users SET is_active = 0 WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

# ==================== COMANDOS DE ADMINISTRADOR ====================
async def genkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ No tienes permisos para usar este comando.")
        return
    
    key = generate_key()
    created_at = datetime.now()
    duration = 30
    
    conn = get_db()
    c = conn.cursor()
    c.execute('''INSERT INTO keys (key, created_by, created_at, duration_days, redeemed)
                 VALUES (?, ?, ?, ?, 0)''', (key, user_id, created_at, duration))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ **Key Generada**\n\n"
        f"🔑 `{key}`\n"
        f"⏱ Duración: {duration} días\n"
        f"📅 Creada: {created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"⚠️ Esta key solo puede usarse una vez.",
        parse_mode='Markdown'
    )

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_group_admin(update, context):
        await update.message.reply_text("❌ Solo los administradores pueden usar este comando.")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Responde al mensaje del usuario que quieres banear.")
        return
    
    user_to_ban = update.message.reply_to_message.from_user
    reason = ' '.join(context.args) if context.args else "Sin razón especificada"
    
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, user_to_ban.id)
        
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO banned_users (user_id, banned_at, reason)
                     VALUES (?, ?, ?)''', (user_to_ban.id, datetime.now(), reason))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Usuario {user_to_ban.first_name} ha sido baneado.\n📝 Razón: {reason}")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Error al banear: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_group_admin(update, context):
        await update.message.reply_text("❌ Solo los administradores pueden usar este comando.")
        return
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /unban <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        await context.bot.unban_chat_member(update.effective_chat.id, user_id)
        
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Usuario con ID {user_id} ha sido desbaneado.")
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Error al desbanear: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_group_admin(update, context):
        await update.message.reply_text("❌ Solo los administradores pueden usar este comando.")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Responde al mensaje del usuario que quieres mutear.")
        return
    
    user_to_mute = update.message.reply_to_message.from_user
    
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            user_to_mute.id,
            {
                'can_send_messages': False,
                'can_send_media_messages': False,
                'can_send_polls': False,
                'can_send_other_messages': False,
                'can_add_web_page_previews': False
            }
        )
        
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO muted_users (user_id, muted_at, expires_at)
                     VALUES (?, ?, ?)''', (user_to_mute.id, datetime.now(), None))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ {user_to_mute.first_name} ha sido muteado.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Error al mutear: {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin_or_group_admin(update, context):
        await update.message.reply_text("❌ Solo los administradores pueden usar este comando.")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ Responde al mensaje del usuario que quieres desmutear.")
        return
    
    user_to_unmute = update.message.reply_to_message.from_user
    
    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            user_to_unmute.id,
            {
                'can_send_messages': True,
                'can_send_media_messages': True,
                'can_send_polls': True,
                'can_send_other_messages': True,
                'can_add_web_page_previews': True
            }
        )
        
        conn = get_db()
        c = conn.cursor()
        c.execute('DELETE FROM muted_users WHERE user_id = ?', (user_to_unmute.id,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ {user_to_unmute.first_name} ha sido desmuteado.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Error al desmutear: {e}")

# ==================== COMANDOS DE USUARIO ====================
async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /redeem <KEY>")
        return
    
    key = context.args[0].upper()
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('SELECT * FROM keys WHERE key = ? AND redeemed = 0', (key,))
    key_data = c.fetchone()
    
    if not key_data:
        await update.message.reply_text("❌ Key inválida o ya canjeada.")
        conn.close()
        return
    
    c.execute('SELECT * FROM users WHERE user_id = ? AND is_active = 1', (user.id,))
    existing_user = c.fetchone()
    
    if existing_user:
        await update.message.reply_text("❌ Ya tienes un plan activo.")
        conn.close()
        return
    
    redeemed_at = datetime.now()
    plan_end = redeemed_at + timedelta(days=key_data[3])
    
    c.execute('''UPDATE keys SET redeemed = 1, redeemed_by = ?, redeemed_at = ?
                 WHERE key = ?''', (user.id, redeemed_at, key))
    
    c.execute('''INSERT OR REPLACE INTO users 
                 (user_id, username, first_name, plan_start, plan_end, is_active, redeemed_key)
                 VALUES (?, ?, ?, ?, ?, 1, ?)''',
              (user.id, user.username, user.first_name, redeemed_at, plan_end, key))
    
    conn.commit()
    conn.close()
    
    try:
        invite_link = await context.bot.create_chat_invite_link(
            GRUPO_VIP_ID,
            member_limit=1,
            expire_date=datetime.now() + timedelta(hours=24)
        )
        
        await update.message.reply_text(
            f"✅ **Key Canjeada Exitosamente**\n\n"
            f"👤 Usuario: {user.first_name}\n"
            f"📅 Plan activo hasta: {plan_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"⏱ Duración: {key_data[3]} días\n\n"
            f"🔗 **Link de acceso al VIP:**\n{invite_link.invite_link}\n\n"
            f"⚠️ Este link expira en 24 horas y solo puede usarse una vez.",
            parse_mode='Markdown'
        )
    except TelegramError:
        await update.message.reply_text(
            f"✅ **Key Canjeada Exitosamente**\n\n"
            f"👤 Usuario: {user.first_name}\n"
            f"📅 Plan activo hasta: {plan_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"⏱ Duración: {key_data[3]} días\n\n"
            f"Contacta a un admin para que te agregue al grupo VIP.",
            parse_mode='Markdown'
        )

async def refe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ? AND is_active = 1', (user.id,))
    user_data = c.fetchone()
    conn.close()
    
    if not user_data:
        await update.message.reply_text("❌ Necesitas tener un plan activo para usar este comando.")
        return
    
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("❌ Responde a una imagen con /refe para reenviarla.")
        return
    
    photo = update.message.reply_to_message.photo[-1]
    
    caption = (
        f"📸 Referencia compartida por: @{user.username or user.first_name}\n\n"
        f"💰 ¿Quieres ganancias así?\n"
        f"📩 Contáctanos para más información"
    )
    
    try:
        await context.bot.send_photo(
            chat_id=GRUPO_REFES_ID,
            photo=photo.file_id,
            caption=caption
        )
        await update.message.reply_text("✅ Imagen reenviada al grupo de referencias.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Error al reenviar: {e}")

async def staff_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff_list = get_staff_list()
    
    if not staff_list:
        await update.message.reply_text("📝 Staff no configurado aún.")
        return
    
    text = "👥 **NUESTRO STAFF** 👥\n\n"
    for name, username, role in staff_list:
        user_mention = f"@{username}" if username else "Sin username"
        text += f"• **{name}**\n  🏷 {role}\n  👤 {user_mention}\n\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    else:
        target_user = user
    
    text = (
        f"🆔 **Información del Usuario**\n\n"
        f"👤 Nombre: {target_user.first_name}\n"
        f"📝 Username: @{target_user.username or 'No tiene'}\n"
        f"🆔 ID: `{target_user.id}`\n"
        f"🤖 Bot: {'Sí' if target_user.is_bot else 'No'}\n"
        f"🌐 Lenguaje: {target_user.language_code or 'Desconocido'}"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE user_id = ?', (user.id,))
    user_data = c.fetchone()
    conn.close()
    
    if not user_data:
        await update.message.reply_text(
            "❌ **No tienes un plan activo**\n\n"
            "Contacta a un administrador para adquirir acceso.",
            parse_mode='Markdown'
        )
        return
    
    is_active = user_data[5]
    plan_end = datetime.fromisoformat(user_data[4]) if user_data[4] else None
    
    if is_active and plan_end and plan_end > datetime.now():
        days_left = (plan_end - datetime.now()).days
        hours_left = (plan_end - datetime.now()).seconds // 3600
        
        text = (
            f"✅ **Plan Activo**\n\n"
            f"👤 Usuario: {user_data[2]}\n"
            f"📅 Inicio: {datetime.fromisoformat(user_data[3]).strftime('%Y-%m-%d %H:%M')}\n"
            f"⏰ Vencimiento: {plan_end.strftime('%Y-%m-%d %H:%M')}\n"
            f"⏳ Tiempo restante: {days_left} días y {hours_left} horas\n\n"
            f"🔑 Key: ||{user_data[6]}||"
        )
    else:
        text = (
            f"❌ **Plan Inactivo o Vencido**\n\n"
            f"Tu plan ha expirado o fue cancelado.\n"
            f"Contacta a un administrador para renovar."
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ==================== EVENTOS ====================
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for new_member in update.message.new_chat_members:
        chat_id = update.effective_chat.id
        
        if chat_id == GRUPO_VIP_ID:
            conn = get_db()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE user_id = ? AND is_active = 1', (new_member.id,))
            user_data = c.fetchone()
            conn.close()
            
            if not user_data:
                try:
                    await context.bot.ban_chat_member(chat_id, new_member.id)
                    await context.bot.unban_chat_member(chat_id, new_member.id)
                    await update.message.reply_text(
                        f"🚫 {new_member.first_name} fue expulsado: No tiene plan activo."
                    )
                except TelegramError:
                    pass
            else:
                await update.message.reply_text(
                    f"🎉 ¡Bienvenido al VIP, {new_member.first_name}!\n\n"
                    f"Disfruta de tu membresía. Usa /plan para ver tus días restantes."
                )
        
        elif chat_id == GRUPO_VENTAS_ID:
            await update.message.reply_text(
                f"👋 ¡Bienvenido, {new_member.first_name}!\n\n"
                f"Este es el grupo de ventas. Contacta a un admin si deseas adquirir acceso VIP."
            )

async def check_expired_plans(context: ContextTypes.DEFAULT_TYPE):
    check_and_update_plans(context)

# ==================== MAIN ====================
def main():
    print("🚀 Iniciando Bot de Comunidad...")
    
    # Inicializar base de datos y staff
    init_db()
    init_staff()
    
    # Crear aplicación
    application = Application.builder().token(TOKEN).build()
    
    # Comandos de administrador
    application.add_handler(CommandHandler("genkey", genkey_command))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("mute", mute_command))
    application.add_handler(CommandHandler("unmute", unmute_command))
    
    # Comandos de usuario
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("refe", refe_command))
    application.add_handler(CommandHandler("staff", staff_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("plan", plan_command))
    
    # Eventos
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    # Job para verificar planes vencidos (cada 1 hora)
    job_queue = application.job_queue
    job_queue.run_repeating(check_expired_plans, interval=3600, first=10)
    
    print("✅ Bot iniciado correctamente. Presiona Ctrl+C para detener.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()