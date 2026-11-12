"""Callback query router for inline buttons."""
from telegram import Update
from telegram.ext import CallbackQueryHandler
from data_catalog import SKILL_BY_KEY
from database import execute, fetchone
from handlers.skills import learn_skill

async def router_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    user_id = update.effective_user.id

    if data.startswith("learn:"):
        skill_key = data.split(":", 1)[1]
        msg = await learn_skill(user_id, skill_key)
        await query.edit_message_text(msg)
        return

    if data == "learn:menu":
        from handlers.skills import learn_cmd
        await learn_cmd(update, context)
        return

    if data == "skillequip:menu":
        from handlers.skills import skill_equip_cmd
        await skill_equip_cmd(update, context)
        return

    if data.startswith("skillset:"):
        parts = data.split(":")
        if len(parts) == 3:
            slot = int(parts[1])
            skill_key = parts[2]
            if skill_key in SKILL_BY_KEY:
                await execute("UPDATE owned_skills SET slot = NULL WHERE user_id = ? AND slot = ?", (user_id, slot))
                await execute("UPDATE owned_skills SET slot = ? WHERE user_id = ? AND skill_key = ?", (slot, user_id, skill_key))
                await query.edit_message_text(f"Equipped {SKILL_BY_KEY[skill_key]['name']} to slot {slot + 1}.")
        return

    await query.edit_message_text("Unknown action.")

def register(app):
    app.add_handler(CallbackQueryHandler(router_callback))
