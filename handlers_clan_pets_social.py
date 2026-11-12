"""Clans with leader protection, pets, leaderboards, titles and settings."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import PET_BY_KEY, PETS, TITLES
from database import execute, fetchone, fetchall, add_inventory, atomic_spend, take_inventory
from handlers.common import clan_of, guard
from utils import NL, DIV, esc, kb, num, short

PET_SUMMON_COST = 120
PET_FEED_XP = 60
DONATION_TIERS = [100, 500, 2000, 10000]
ROLE_ORDER = {"Leader": 0, "Officer": 1, "Member": 2}


async def clan_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    clan = await clan_of(user['user_id'])
    if not clan:
        return await update.effective_message.reply_text(
            f"🛡 <b>You are not in a clan</b>{NL}"
            "Create one with <code>/clan_create Name</code>, or browse the ranking with /clan_top.",
            parse_mode=ParseMode.HTML)
    members = await fetchall(
        "SELECT u.display_name, m.role, u.level FROM clan_members m JOIN users u ON u.user_id=m.user_id "
        "WHERE m.clan_id=? ORDER BY u.level DESC", (clan['clan_id'],))
    lines = [f"🏰 <b>{esc(clan['name'])}</b> · level {clan['level']}",
             f"Treasury 🪙 {num(clan['treasury'])} · clan XP {num(clan['xp'])}",
             DIV, f"Members ({len(members)}):"]
    for member in members[:20]:
        lines.append(f"• {esc(member['display_name'])} — {member['role']} · Lv.{member['level']}")
    rows = [[("Donate 100", "clandonate:100"), ("Donate 500", "clandonate:500")],
            [("Donate 2000", "clandonate:2000"), ("Donate 10000", "clandonate:10000")]]
    if clan['role'] == 'Leader':
        rows.append([("👑 Leadership", "clan:promote"), ("💥 Disband", "clan:disband")])
    rows.append([("🚪 Leave clan", "clan:leave")])
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def clan_create_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    name = " ".join(context.args).strip()
    if not name:
        return await update.effective_message.reply_text("Usage: <code>/clan_create Name</code>", parse_mode=ParseMode.HTML)
    if len(name) > 28:
        return await update.effective_message.reply_text("Clan names are limited to 28 characters.")
    if await clan_of(user['user_id']):
        return await update.effective_message.reply_text("You already belong to a clan.")
    if user['coins'] < 1000:
        return await update.effective_message.reply_text("Creating a clan costs 1000 coins.")
    if await fetchone("SELECT 1 FROM clans WHERE name=?", (name,)):
        return await update.effective_message.reply_text("That clan name is taken.")
    if not await atomic_spend(user['user_id'], 'coins', 1000):
        return await update.effective_message.reply_text("Not enough coins.")
    clan_id, _ = await execute("INSERT INTO clans(name, leader_id) VALUES(?,?)", (name, user['user_id']))
    await execute("INSERT INTO clan_members(user_id, clan_id, role) VALUES(?,?,'Leader')",
                  (user['user_id'], clan_id))
    await update.effective_message.reply_text(f"🏰 Clan <b>{esc(name)}</b> founded. You are the leader.",
                                              parse_mode=ParseMode.HTML)


async def donate(user_id: int, amount: int) -> str:
    if amount not in DONATION_TIERS:
        return "Pick one of the donation tiers."
    clan = await clan_of(user_id)
    if not clan:
        return "Join a clan first."
    if not await atomic_spend(user_id, 'coins', amount):
        return "Not enough coins."
    await execute("UPDATE clans SET treasury=treasury+?, xp=xp+? WHERE clan_id=?",
                  (amount, amount // 5, clan['clan_id']))
    await execute("UPDATE users SET donations=donations+? WHERE user_id=?", (amount, user_id))
    level_row = await fetchone("SELECT xp FROM clans WHERE clan_id=?", (clan['clan_id'],))
    if level_row['xp'] >= clan['level'] * 5000:
        await execute("UPDATE clans SET level=level+1, xp=xp-? WHERE clan_id=?",
                      (clan['level'] * 5000, clan['clan_id']))
        return f"Donated {num(amount)} coins. The clan reached level {clan['level'] + 1}!"
    return f"Donated {num(amount)} coins to {clan['name']}."


async def leave_prompt(message, user_id: int):
    clan = await clan_of(user_id)
    if not clan:
        return await message.reply_text("You are not in a clan.")
    if clan['role'] == 'Leader':
        members = await fetchall(
            "SELECT u.display_name, m.user_id FROM clan_members m JOIN users u ON u.user_id=m.user_id "
            "WHERE m.clan_id=? AND m.user_id!=?", (clan['clan_id'], user_id))
        rows = [[(f"👑 Promote {short(m['display_name'], 20)}", f"clanpromote:{m['user_id']}")] for m in members]
        rows.append([("💥 Disband clan", "clan:disband")])
        rows.append([("⬅ Back", "clan:panel")])
        return await message.reply_text(
            f"👑 <b>Leader protection</b>{NL}As leader you cannot simply leave {esc(clan['name'])}. "
            f"Promote a member to leader, or disband the clan.",
            parse_mode=ParseMode.HTML, reply_markup=kb(rows))
    await message.reply_text(
        f"⚠️ Leave <b>{esc(clan['name'])}</b>? Your donations are not refunded.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb([[("✅ Yes, leave", "clanleave:yes"), ("❌ Cancel", "clan:panel")]]))


async def leave_clan(user_id: int) -> str:
    clan = await clan_of(user_id)
    if not clan:
        return "You are not in a clan."
    if clan['role'] == 'Leader':
        return "Leaders must promote a successor or disband the clan."
    await execute("DELETE FROM clan_members WHERE user_id=?", (user_id,))
    return f"You left {clan['name']}."


async def promote_prompt(message, user_id: int):
    clan = await clan_of(user_id)
    if not clan or clan['role'] != 'Leader':
        return await message.reply_text("Only the clan leader can transfer leadership.")
    members = await fetchall(
        "SELECT u.display_name, m.user_id FROM clan_members m JOIN users u ON u.user_id=m.user_id "
        "WHERE m.clan_id=? AND m.user_id!=?", (clan['clan_id'], user_id))
    if not members:
        return await message.reply_text("You have no members to promote yet.")
    rows = [[(f"👑 {short(m['display_name'], 22)}", f"clanpromote:{m['user_id']}")] for m in members]
    await message.reply_text("Choose the new leader:", reply_markup=kb(rows))


async def promote(user_id: int, target_id: int) -> str:
    clan = await clan_of(user_id)
    if not clan or clan['role'] != 'Leader':
        return "Only the clan leader can transfer leadership."
    target = await fetchone("SELECT 1 FROM clan_members WHERE clan_id=? AND user_id=?",
                            (clan['clan_id'], target_id))
    if not target:
        return "That player is not in your clan."
    await execute("UPDATE clan_members SET role='Member' WHERE user_id=?", (user_id,))
    await execute("UPDATE clan_members SET role='Leader' WHERE user_id=?", (target_id,))
    await execute("UPDATE clans SET leader_id=? WHERE clan_id=?", (target_id, clan['clan_id']))
    return "Leadership transferred. You are now a member."


async def disband_prompt(message, user_id: int):
    clan = await clan_of(user_id)
    if not clan or clan['role'] != 'Leader':
        return await message.reply_text("Only the clan leader can disband the clan.")
    await message.reply_text(
        f"💥 Disband <b>{esc(clan['name'])}</b>? This permanently deletes the clan and its treasury.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb([[("💥 Confirm disband", "clandisband:yes"), ("❌ Cancel", "clan:panel")]]))


async def disband(user_id: int) -> str:
    clan = await clan_of(user_id)
    if not clan or clan['role'] != 'Leader':
        return "Only the clan leader can disband the clan."
    await execute("DELETE FROM clans WHERE clan_id=?", (clan['clan_id'],))
    return f"{clan['name']} was disbanded."


async def clan_top_cmd(update, context):
    await guard(update)
    rows = await fetchall("SELECT name, level, treasury FROM clans ORDER BY level DESC, treasury DESC LIMIT 15")
    if not rows:
        return await update.effective_message.reply_text("No clans exist yet. Create the first one!")
    lines = ["🏆 <b>Clan ranking</b>", DIV]
    for i, row in enumerate(rows, 1):
        lines.append(f"{i}. {esc(row['name'])} · Lv.{row['level']} · 🪙 {num(row['treasury'])}")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)


async def pets_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    owned = await fetchall("SELECT * FROM pets WHERE user_id=? ORDER BY level DESC", (user['user_id'],))
    lines = [f"🐾 <b>Companions</b> · {len(owned)} owned", DIV]
    for row in owned:
        pet = PET_BY_KEY.get(row['pet_key'])
        if not pet:
            continue
        mark = " ✅ active" if row['equipped'] else ""
        lines.append(f"• {esc(pet['name'])} · Lv.{row['level']} · +{pet['bonus']}% {pet['bonus_type']}{mark}")
    if len(lines) == 2:
        lines.append("No companions yet. Summon one below.")
    rows = [[(f"🥚 Summon pet · {PET_SUMMON_COST} 💎", "petsummon")]]
    for row in owned[:10]:
        pet = PET_BY_KEY.get(row['pet_key'])
        if not pet:
            continue
        rows.append([(f"Equip {short(pet['name'], 18)}", f"petequip:{pet['key']}"),
                     ("Feed", f"petfeed:{pet['key']}")])
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def summon_pet(user_id: int) -> str:
    import random
    if not await atomic_spend(user_id, 'gems', PET_SUMMON_COST):
        return f"Summoning a pet costs {PET_SUMMON_COST} 💎."
    pet = random.choice(PETS)
    owned = await fetchone("SELECT level FROM pets WHERE user_id=? AND pet_key=?", (user_id, pet['key']))
    if owned:
        await execute("UPDATE pets SET level=level+1 WHERE user_id=? AND pet_key=?", (user_id, pet['key']))
        return f"{pet['name']} returned and reached level {owned['level'] + 1}."
    await execute("INSERT INTO pets(user_id, pet_key) VALUES(?,?)", (user_id, pet['key']))
    return f"🐣 A {pet['name']} joined you! Bonus +{pet['bonus']}% {pet['bonus_type']}."


async def equip_pet(user_id: int, pet_key: str) -> str:
    owned = await fetchone("SELECT 1 FROM pets WHERE user_id=? AND pet_key=?", (user_id, pet_key))
    if not owned:
        return "You do not own that companion."
    await execute("UPDATE pets SET equipped=0 WHERE user_id=?", (user_id,))
    await execute("UPDATE pets SET equipped=1 WHERE user_id=? AND pet_key=?", (user_id, pet_key))
    return f"{PET_BY_KEY[pet_key]['name']} is now your active companion."


async def feed_pet(user_id: int, pet_key: str) -> str:
    owned = await fetchone("SELECT level FROM pets WHERE user_id=? AND pet_key=?", (user_id, pet_key))
    if not owned:
        return "You do not own that companion."
    rows = await fetchall("SELECT item_key FROM inventory WHERE user_id=? AND quantity>0", (user_id,))
    food_key = None
    from data_catalog import ITEM_BY_KEY
    for row in rows:
        item = ITEM_BY_KEY.get(row['item_key'])
        if item and item.get('effect') == 'pet_food':
            food_key = row['item_key']
            break
    if not food_key:
        return "You need pet food. Buy some in /shop."
    if not await take_inventory(user_id, food_key, 1):
        return "You need pet food."
    from game import grant_xp
    await execute("UPDATE pets SET level=level+1 WHERE user_id=? AND pet_key=?", (user_id, pet_key))
    await grant_xp(user_id, PET_FEED_XP)
    return f"{PET_BY_KEY[pet_key]['name']} reached level {owned['level'] + 1}!"


async def top_cmd(update, context):
    await guard(update)
    fields = {"level": "Level", "coins": "Coins", "gems": "Gems", "pve_wins": "PvE wins",
              "pvp_wins": "PvP wins", "boss_wins": "Boss wins"}
    rows = [[(label, f"top:{field}")] for field, label in fields.items()]
    await update.effective_message.reply_text("🏆 Choose a leaderboard:", reply_markup=kb(rows))


async def titles_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{t['name']} · {t['criterion']} {t['value']}", f"title:{t['name']}")] for t in TITLES]
    await update.effective_message.reply_text(
        f"🎖 <b>Titles</b>{NL}Current title: {esc(user['title'])}{NL}Tap a title to display it.",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def set_title(user_id: int, name: str) -> str:
    title = next((t for t in TITLES if t['name'] == name), None)
    if not title:
        return "Unknown title."
    user = await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
    value = user.get(title['criterion'], 0)
    if isinstance(value, int) and value < title['value']:
        return f"You need {title['criterion']} {title['value']} for that title."
    await execute("UPDATE users SET title=? WHERE user_id=?", (name, user_id))
    return f"Your title is now {name}."


async def settings_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    await update.effective_message.reply_text(
        f"⚙ <b>Settings</b>{NL}Notifications: {'on' if user['notifications'] else 'off'}",
        parse_mode=ParseMode.HTML,
        reply_markup=kb([[("Toggle notifications", "settings:toggle")]]))


def register(app):
    for name, fn in [("clan", clan_cmd), ("clan_create", clan_create_cmd), ("clan_leave", clan_cmd),
                     ("clan_donate", clan_cmd), ("clanraid", clan_cmd), ("clan_top", clan_top_cmd),
                     ("pets", pets_cmd), ("pet", pets_cmd), ("pet_equip", pets_cmd),
                     ("pet_feed", pets_cmd), ("pet_summon", pets_cmd),
                     ("top", top_cmd), ("leaderboard", top_cmd), ("titles", titles_cmd),
                     ("settings", settings_cmd)]:
        app.add_handler(CommandHandler(name, fn))
