"""Common handler helpers."""
from telegram import Update
from database import fetchone

async def guard(update: Update):
    user = update.effective_user
    if not user:
        return None
    row = await fetchone(
        "SELECT * FROM players WHERE user_id=?", (user.id,)
    )
    if not row:
        await update.effective_message.reply_text("Use /start first.")
        return None
    return row
