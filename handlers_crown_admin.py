"""Admin tooling: dashboard, grants, moderation, broadcast and artwork manager."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import (CHARACTERS, CHARACTERS_BY_SERIES, CATALOG_COUNTS, ITEMS, ITEM_BY_KEY,
                          PET_BY_KEY, PETS, SERIES)
from database import execute, fetchone, fetchall, add_inventory
from handlers.common import guard, is_admin, require_admin
from utils import NL, DIV, esc, kb, num, short

ART_CATEGORIES = {
    "hero": "Heroes",
    "boss": "Bosses",
    "npc": "NPCs",
    "pet": "Pets",
    "region": "Regions",
    "banner": "Banners",
}


async def admin_cmd(update, context):
    user = await require_admin(update)
    if not user:
        return
    totals = await fetchone(
        "SELECT COUNT(*) players, SUM(banned) banned, SUM(coins) coins, SUM(gems) gems FROM users")
    battles = await fetchone("SELECT COUNT(*) n FROM battles WHERE state='active'")
    clans = await fetchone("SELECT COUNT(*) n FROM clans")
    listings = await fetchone("SELECT COUNT(*) n FROM market_listings WHERE active=1")
    lines = [
        "🛠 <b>Admin dashboard</b>", DIV,
        f"Players: {num(totals['players'])} · banned: {num(totals['banned'] or 0)}",
        f"Coins in circulation: {num(totals['coins'] or 0)}",
        f"Gems in circulation: {num(totals['gems'] or 0)}",
        f"Active battles: {battles['n']} · clans: {clans['n']} · market listings: {listings['n']}",
        DIV,
        f"Catalog: {CATALOG_COUNTS['characters_total']} characters · "
        f"{len(ITEMS)} items · {len(PETS)} pets",
        DIV,
        "<b>Commands</b>",
        "/give &lt;id&gt; &lt;coins|gems&gt; &lt;amount&gt;",
        "/setlevel &lt;id&gt; &lt;level&gt;",
        "/grantchar &lt;id&gt; &lt;char_key&gt;",
        "/grantitem &lt;id&gt; &lt;item_key&gt; &lt;qty&gt;",
        "/ban &lt;id&gt; · /unban &lt;id&gt;",
        "/broadcast &lt;text&gt;",
        "/crown · /upload · /artlist",
    ]
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)


async def give_cmd(update, context):
    if not await require_admin(update):
        return
    try:
        target = int(context.args[0]); field = context.args[1].lower(); amount = int(context.args[2])
    except (IndexError, ValueError):
        return await update.effective_message.reply_text(
            "Usage: <code>/give user_id coins|gems amount</code>", parse_mode=ParseMode.HTML)
    if field not in ("coins", "gems") or not (0 < amount <= 10_000_000):
        return await update.effective_message.reply_text("Invalid currency or amount.")
    _, changed = await execute(f"UPDATE users SET {field}={field}+? WHERE user_id=?", (amount, target))
    await update.effective_message.reply_text(
        f"Granted {num(amount)} {field}." if changed else "Player not found.")


async def setlevel_cmd(update, context):
    if not await require_admin(update):
        return
    try:
        target = int(context.args[0]); level = max(1, min(200, int(context.args[1])))
    except (IndexError, ValueError):
        return await update.effective_message.reply_text("Usage: <code>/setlevel user_id level</code>",
                                                        parse_mode=ParseMode.HTML)
    _, changed = await execute("UPDATE users SET level=?, xp=0 WHERE user_id=?", (level, target))
    await update.effective_message.reply_text(
        f"Level set to {level}." if changed else "Player not found.")


async def grantchar_cmd(update, context):
    if not await require_admin(update):
        return
    try:
        target = int(context.args[0]); char_key = context.args[1]
    except (IndexError, ValueError):
        return await update.effective_message.reply_text(
            "Usage: <code>/grantchar user_id char_key</code>", parse_mode=ParseMode.HTML)
    from data_catalog import CHARACTER_BY_KEY
    if char_key not in CHARACTER_BY_KEY:
        return await update.effective_message.reply_text("Unknown character key.")
    await execute("INSERT OR IGNORE INTO owned_characters(user_id, char_key) VALUES(?,?)", (target, char_key))
    await update.effective_message.reply_text(f"Granted {CHARACTER_BY_KEY[char_key]['name']}.")


async def grantitem_cmd(update, context):
    if not await require_admin(update):
        return
    try:
        target = int(context.args[0]); item_key = context.args[1]; qty = int(context.args[2]) if len(context.args) > 2 else 1
    except (IndexError, ValueError):
        return await update.effective_message.reply_text(
            "Usage: <code>/grantitem user_id item_key qty</code>", parse_mode=ParseMode.HTML)
    if item_key not in ITEM_BY_KEY:
        return await update.effective_message.reply_text("Unknown item key.")
    await add_inventory(target, item_key, max(1, qty))
    await update.effective_message.reply_text(f"Granted {qty}× {ITEM_BY_KEY[item_key]['name']}.")


async def ban_cmd(update, context):
    if not await require_admin(update):
        return
    try:
        target = int(context.args[0])
    except (IndexError, ValueError):
        return await update.effective_message.reply_text("Usage: <code>/ban user_id</code>", parse_mode=ParseMode.HTML)
    _, changed = await execute("UPDATE users SET banned=1 WHERE user_id=?", (target,))
    await update.effective_message.reply_text("Player banned." if changed else "Player not found.")


async def unban_cmd(update, context):
    if not await require_admin(update):
        return
    try:
        target = int(context.args[0])
    except (IndexError, ValueError):
        return await update.effective_message.reply_text("Usage: <code>/unban user_id</code>", parse_mode=ParseMode.HTML)
    _, changed = await execute("UPDATE users SET banned=0 WHERE user_id=?", (target,))
    await update.effective_message.reply_text("Player unbanned." if changed else "Player not found.")


async def broadcast_cmd(update, context):
    if not await require_admin(update):
        return
    text = " ".join(context.args).strip()
    if not text:
        return await update.effective_message.reply_text("Usage: <code>/broadcast message</code>", parse_mode=ParseMode.HTML)
    players = await fetchall("SELECT user_id FROM users WHERE banned=0")
    sent = failed = 0
    for row in players:
        try:
            await context.bot.send_message(row['user_id'], f"📢 <b>Announcement</b>{NL}{esc(text)}",
                                           parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            failed += 1
    await update.effective_message.reply_text(f"Broadcast sent to {sent} players ({failed} failed).")


async def crown_cmd(update, context):
    user = await require_admin(update)
    if not user:
        return
    art = {(row['entity_key'], row['category']) for row in
           await fetchall("SELECT entity_key, category FROM custom_art")}
    lines = ["👑 <b>Crown · media manager</b>", DIV]
    for series in SERIES:
        chars = CHARACTERS_BY_SERIES[series['id']]
        have = sum(1 for c in chars if (c['key'], 'Heroes') in art)
        lines.append(f"{esc(series['name'])} — {have}/{len(chars)} heroes have art")
    lines.append(DIV)
    lines.append("Reply to a photo with <code>/upload &lt;entity_key&gt;</code>")
    lines.append("Categories: " + ", ".join(f"{k}={v}" for k, v in ART_CATEGORIES.items()))
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)


async def upload_cmd(update, context):
    user = await require_admin(update)
    if not user:
        return
    message = update.effective_message
    reply = message.reply_to_message
    args = list(context.args)
    if not reply or not reply.photo or not args:
        return await message.reply_text(
            "Reply to a photo with <code>/upload entity_key [category]</code>", parse_mode=ParseMode.HTML)
    entity_key = args[0]
    category = ART_CATEGORIES.get((args[1].lower() if len(args) > 1 else 'hero'), 'Heroes')
    await execute(
        "INSERT INTO custom_art(entity_key,category,file_id,uploader_id) VALUES(?,?,?,?) "
        "ON CONFLICT(entity_key) DO UPDATE SET file_id=excluded.file_id, category=excluded.category, "
        "uploader_id=excluded.uploader_id, updated_at=CURRENT_TIMESTAMP",
        (entity_key, category, reply.photo[-1].file_id, user['user_id']))
    await message.reply_text(f"✅ Art saved for <code>{esc(entity_key)}</code> ({category}).",
                             parse_mode=ParseMode.HTML)


async def artlist_cmd(update, context):
    if not await require_admin(update):
        return
    rows = await fetchall("SELECT entity_key, category, updated_at FROM custom_art ORDER BY updated_at DESC LIMIT 25")
    if not rows:
        return await update.effective_message.reply_text("No artwork uploaded yet.")
    lines = ["🖼 <b>Uploaded art</b>", DIV]
    for row in rows:
        lines.append(f"• {esc(row['entity_key'])} — {row['category']}")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)


async def catalog_cmd(update, context):
    await guard(update)
    lines = ["📚 <b>Content catalog</b>", DIV]
    for series in SERIES:
        lines.append(f"{esc(series['name'])}: {series['requested_count']} characters")
    lines.append(DIV)
    lines.append(f"Characters total: {CATALOG_COUNTS['characters_total']}")
    lines.append(f"Weapons per world: {CATALOG_COUNTS['weapons_per_world']} · "
                 f"Armor per world: {CATALOG_COUNTS['armor_per_world']}")
    lines.append(f"Skills per world: {CATALOG_COUNTS['skills_per_world']}")
    lines.append(f"Items per world: {CATALOG_COUNTS['items_per_world']} · NPCs: {CATALOG_COUNTS['npcs_per_world']}")
    lines.append(f"Bosses per world: {CATALOG_COUNTS['bosses_per_world']} · "
                 f"Enemies: {CATALOG_COUNTS['enemies_per_world']}")
    lines.append(f"Pets per world: {CATALOG_COUNTS['pets_per_world']} · "
                 f"Regions: {CATALOG_COUNTS['regions_per_world']} · Dungeons: {CATALOG_COUNTS['dungeons_per_world']}")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)


def register(app):
    for name, fn in [("admin", admin_cmd), ("give", give_cmd), ("setlevel", setlevel_cmd),
                     ("grantchar", grantchar_cmd), ("grantitem", grantitem_cmd),
                     ("ban", ban_cmd), ("unban", unban_cmd), ("broadcast", broadcast_cmd),
                     ("crown", crown_cmd), ("upload", upload_cmd), ("artlist", artlist_cmd),
                     ("catalog", catalog_cmd)]:
        app.add_handler(CommandHandler(name, fn))
