"""Entry point: builds the bot application and registers every handler module."""
from __future__ import annotations
import logging
from datetime import date
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler
from config import BOT_TOKEN
from data_catalog import CATALOG_COUNTS, SERIES
from database import execute, fetchall, init_db, ensure_user
from game import MAX_ENERGY, refresh_energy
from handlers import characters, clan_pets_social, combat_world, crown_admin, gacha_market
from handlers import inventory_gear, router, skills
from handlers.common import guard, is_admin
from utils import NL, DIV, esc, kb, num

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s — %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("anime-rpg")


async def start_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    worlds = ", ".join(s['name'] for s in SERIES)
    text = (
        f"🏯 <b>Welcome to Anime RPG</b>" + NL + DIV + NL +
        f"{esc(user['display_name'])}, your account is ready." + NL + NL +
        f"This build ships <b>{CATALOG_COUNTS['characters_total']}</b> collectible characters across "
        f"{len(SERIES)} worlds ({esc(worlds)}), "
        f"{CATALOG_COUNTS['weapons_per_world']} weapons and {CATALOG_COUNTS['armor_per_world']} armor pieces "
        f"per world, {CATALOG_COUNTS['skills_per_world']} skills per world, dungeons, bosses, pets, "
        f"clans, a player market and a full admin toolkit." + NL + DIV + NL +
        "Every battle is manual: you choose each action on the battle card." + NL +
        "Use /help for the full command list, or tap a button below."
    )
    rows = [
        [("🪪 Profile", "menu:profile"), ("👥 Characters", "menu:chars")],
        [("⚔ Hunt", "menu:hunt"), ("🏰 Dungeon", "menu:dungeon")],
        [("🔮 Summon", "banner:list"), ("⚖ Market", "market:list")],
        [("🎒 Inventory", "menu:inv"), ("🛒 Shop", "menu:shop")],
        [("🐾 Pets", "menu:pets"), ("🏰 Clan", "menu:clan")],
        [("📚 Catalog", "menu:catalog"), ("📖 Skills", "menu:skills")],
    ]
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def help_cmd(update, context):
    if not await guard(update):
        return
    text = (
        "📖 <b>Command reference</b>" + NL + DIV + NL +
        "<b>Profile</b>" + NL +
        "/start · /help · /profile · /daily · /catalog" + NL + NL +
        "<b>Characters</b>" + NL +
        "/characters · /character [name] · /team · /equipchar · /levelup" + NL + NL +
        "<b>Combat</b>" + NL +
        "/hunt · /explore · /dungeon · /boss · /travel · /world · /npc" + NL + NL +
        "<b>Items</b>" + NL +
        "/inv · /gear · /shop · /enhance · /forge" + NL + NL +
        "<b>Skills</b>" + NL +
        "/skills · /learn · /skill_equip" + NL + NL +
        "<b>Summon & market</b>" + NL +
        "/banner · /gacha · /market · /market_sell · /market_cancel" + NL + NL +
        "<b>Social</b>" + NL +
        "/clan · /clan_create · /clan_leave · /clan_top · /pets · /pet · /top · /titles · /settings" + NL + NL +
        "<b>Admin</b>" + NL +
        "/admin · /give · /setlevel · /grantchar · /grantitem · /ban · /unban "
        "/broadcast · /crown · /upload · /artlist"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def daily_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    today = date.today().isoformat()
    if user['daily_date'] == today:
        return await update.effective_message.reply_text("🎁 You already claimed today's reward. Come back tomorrow.")
    yesterday = (date.today().toordinal() - 1)
    streak = user['daily_streak'] + 1 if user['daily_date'] and \
        date.fromisoformat(user['daily_date']).toordinal() == yesterday else 1
    coins = 150 + min(streak, 7) * 40
    gems = 10 + min(streak, 7) * 2
    await execute(
        "UPDATE users SET coins=coins+?, gems=gems+?, energy=MIN(?, energy+5), daily_date=?, daily_streak=? "
        "WHERE user_id=?",
        (coins, gems, MAX_ENERGY, today, streak, user['user_id']))
    await update.effective_message.reply_text(
        f"🎁 <b>Daily reward</b>" + NL +
        f"+{num(coins)} coins · +{num(gems)} gems · +5 energy" + NL +
        f"Login streak: {streak} day(s).",
        parse_mode=ParseMode.HTML)


async def error_handler(update, context):
    log.exception("Update failed", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Something went wrong while processing that action. Please try again.")
        except Exception:
            pass


async def post_init(app: Application):
    await init_db()
    log.info("Database ready. %s characters loaded.", CATALOG_COUNTS['characters_total'])


def build_app() -> Application:
    if not BOT_TOKEN or BOT_TOKEN.startswith("put_your"):
        raise RuntimeError("Set BOT_TOKEN in your local .env file before starting the bot.")
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("daily", daily_cmd))
    characters.register(app)
    combat_world.register(app)
    inventory_gear.register(app)
    skills.register(app)
    gacha_market.register(app)
    clan_pets_social.register(app)
    crown_admin.register(app)
    router.register(app)
    app.add_error_handler(error_handler)
    return app


if __name__ == "__main__":
    application = build_app()
    log.info("Starting long polling…")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
