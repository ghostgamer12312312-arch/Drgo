"""Inventory, gear, enhancement, crafting and the item shop."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import (GEAR, ITEM_BY_KEY, ITEMS, RECIPES, SERIES, SERIES_BY_ID)
from database import execute, fetchone, fetchall, add_inventory, take_inventory, atomic_spend
from handlers.common import guard
from utils import NL, DIV, esc, kb, num, short

ENHANCE_STONE = "enhance_stone"
MAX_ENHANCE = 10


def _slot_name(slot: str) -> str:
    return {"Weapon": "⚔ Weapon", "Armor": "🛡 Armor"}.get(slot, slot)


async def inventory_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall(
        "SELECT item_key, quantity, equipped_slot, enhancement FROM inventory "
        "WHERE user_id=? AND quantity>0 ORDER BY item_key", (user['user_id'],))
    gear_rows = [r for r in rows if ITEM_BY_KEY.get(r['item_key'], {}).get('type') == 'gear']
    other_rows = [r for r in rows if ITEM_BY_KEY.get(r['item_key'], {}).get('type') != 'gear']
    lines = [f"🎒 <b>Inventory</b> · {esc(user['display_name'])}", DIV,
             f"🪙 {num(user['coins'])} · 💎 {num(user['gems'])} · ⚡ {user['energy']}/10"]
    if gear_rows:
        lines.append(DIV + NL + "<b>Gear</b>")
        for row in gear_rows[:15]:
            item = ITEM_BY_KEY[row['item_key']]
            mark = f" ✅ {row['equipped_slot']} +{row['enhancement']}" if row['equipped_slot'] else ""
            lines.append(f"• {esc(item['name'])} ×{row['quantity']}{mark}")
    if other_rows:
        lines.append(DIV + NL + "<b>Items</b>")
        for row in other_rows[:20]:
            item = ITEM_BY_KEY[row['item_key']]
            lines.append(f"• {esc(item['name'])} ×{row['quantity']}")
    if not gear_rows and not other_rows:
        lines.append(DIV + NL + "Your bag is empty. Visit /shop.")
    buttons = [[("⚔ Equip gear", "gear:menu"), ("🛡 Unequip", "gear:unequip")],
               [("⚗ Enhancement", "enhance:menu"), ("🔨 Crafting", "craft:menu")],
               [("🛒 Shop", "menu:shop")]]
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML, reply_markup=kb(buttons))


async def gear_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall(
        "SELECT item_key, quantity, equipped_slot, enhancement FROM inventory "
        "WHERE user_id=? AND quantity>0", (user['user_id'],))
    buttons = []
    for row in rows:
        item = ITEM_BY_KEY.get(row['item_key'])
        if not item or item['type'] != 'gear':
            continue
        label = f"{_slot_name(item['slot'])} · {short(item['name'], 20)}"
        if row['equipped_slot']:
            buttons.append([(label + " ✅", None)])
        else:
            buttons.append([(label, f"equip:{row['item_key']}")])
    equipped = [r for r in rows if r['equipped_slot']]
    lines = ["🛡 <b>Gear management</b>", DIV]
    lines.append("Equipped: " + (", ".join(f"{r['equipped_slot']} +{r['enhancement']}" for r in equipped) or "nothing"))
    lines.append("Tap an item to equip it. Equipping replaces the same slot.")
    active = [[r for r in row if r[1]] for row in buttons]
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML, reply_markup=kb(active))


async def equip_gear(user_id: int, item_key: str) -> str:
    item = ITEM_BY_KEY.get(item_key)
    if not item or item['type'] != 'gear':
        return "That is not equippable gear."
    owned = await fetchone("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?", (user_id, item_key))
    if not owned or owned['quantity'] < 1:
        return "You do not own that item."
    await execute("UPDATE inventory SET equipped_slot=NULL WHERE user_id=? AND equipped_slot=?", (user_id, item['slot']))
    await execute("UPDATE inventory SET equipped_slot=? WHERE user_id=? AND item_key=?", (item['slot'], user_id, item_key))
    return f"Equipped {item['name']} to {item['slot']}."


async def unequip_menu(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall(
        "SELECT item_key, equipped_slot FROM inventory WHERE user_id=? AND equipped_slot IS NOT NULL",
        (user['user_id'],))
    buttons = [[(f"Unequip {row['equipped_slot']}", f"unequip:{row['item_key']}")] for row in rows]
    await update.effective_message.reply_text(
        "Pick a slot to unequip:" if buttons else "Nothing is equipped.", reply_markup=kb(buttons) if buttons else None)


async def use_item(user_id: int, item_key: str, in_battle: bool = False) -> str:
    item = ITEM_BY_KEY.get(item_key)
    if not item or item['type'] != 'consumable':
        return "That item cannot be used."
    if not await take_inventory(user_id, item_key, 1):
        return "You do not have that item."
    effect, amount = item['effect'], item['amount']
    if effect == 'heal':
        if in_battle:
            await execute("UPDATE battles SET player_hp=MIN(player_max_hp, player_hp+?) WHERE user_id=?", (amount, user_id))
            return f"Recovered up to {amount} HP."
        await execute("UPDATE battles SET player_hp=player_max_hp WHERE user_id=? AND state='active'", (user_id,))
        return f"Used {item['name']}. Your next battle starts at full HP."
    if effect == 'energy':
        await execute("UPDATE users SET energy=MIN(10, energy+?) WHERE user_id=?", (max(1, amount // 5), user_id))
        return "Energy restored."
    if effect == 'xp':
        from game import grant_xp
        gained = await grant_xp(user_id, amount)
        return f"Gained {amount} XP." + (f" Level up x{gained}." if gained else "")
    if effect == 'coins':
        await execute("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, user_id))
        return f"Received {amount} coins."
    if effect == 'revive':
        revived = await execute(
            "UPDATE battles SET player_hp=player_max_hp, state='active' WHERE user_id=? AND state='lost'", (user_id,))
        return "Revived with full HP!" if revived[1] else "No defeat to recover from."
    if effect in ('shield', 'buff', 'defense'):
        await execute("UPDATE battles SET player_hp=MIN(player_max_hp, player_hp+?) WHERE user_id=?", (amount // 2, user_id))
        return "Guard strengthened."
    if effect == 'crit':
        return "Critical oil applied to your next strike."
    if effect == 'ultimate':
        await execute("UPDATE battles SET ultimate=MIN(100, ultimate+?) WHERE user_id=?", (max(10, amount // 3), user_id))
        return "Ultimate gauge charged."
    return f"Used {item['name']}."


async def shop_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{s['name']} items", f"shop:{s['id']}:0")] for s in SERIES]
    rows.append([("🧪 Universal goods", "shop:all:0")])
    await update.effective_message.reply_text(
        f"🛒 <b>Shop</b>{NL}Coins 🪙 {num(user['coins'])} · Gems 💎 {num(user['gems'])}{NL}Pick a catalogue:",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


def shop_page(series_id: str, page: int = 0):
    pool = [i for i in ITEMS if (series_id == 'all' and i['series'] == 'all') or i['series'] == series_id]
    per_page = 8
    total = max(1, (len(pool) + per_page - 1) // per_page)
    page = max(0, min(page, total - 1))
    shown = pool[page * per_page:(page + 1) * per_page]
    rows = [[(f"{short(i['name'], 26)} · {num(i['price'])}🪙", f"buy:{i['key']}")] for i in shown]
    nav = []
    if page > 0:
        nav.append(("⬅ Prev", f"shop:{series_id}:{page - 1}"))
    if page + 1 < total:
        nav.append(("Next ➡", f"shop:{series_id}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([("⬅ Catalogues", "shop:root:0")])
    title = SERIES_BY_ID.get(series_id, {}).get('name', "Universal goods") if series_id != 'all' else "Universal goods"
    return f"🛒 <b>{esc(title)}</b> · page {page + 1}/{total}", rows


async def buy_item(user_id: int, item_key: str) -> str:
    item = ITEM_BY_KEY.get(item_key)
    if not item:
        return "Unknown item."
    if await fetchone("SELECT 1 FROM inventory WHERE user_id=? AND item_key=?", (user_id, item_key)):
        pass
    if item['price'] <= 0:
        return "That item is not sold for coins."
    if not await atomic_spend(user_id, 'coins', item['price']):
        return "Not enough coins."
    await add_inventory(user_id, item_key, 1)
    await execute("INSERT INTO transactions(user_id,kind,amount,note) VALUES(?,?,?,?)",
                  (user_id, 'shop_purchase', -item['price'], item['name']))
    return f"Bought {item['name']} for {num(item['price'])} coins."


async def find_material(user_id: int, effect: str):
    """Return (item_key, quantity) of any owned material with the given effect."""
    rows = await fetchall(
        "SELECT item_key, quantity FROM inventory WHERE user_id=? AND quantity>0", (user_id,))
    for row in rows:
        item = ITEM_BY_KEY.get(row['item_key'])
        if item and item.get('effect') == effect:
            return row['item_key'], row['quantity']
    return None, 0


async def enhance_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall(
        "SELECT item_key, enhancement FROM inventory WHERE user_id=? AND enhancement<?", (user['user_id'], MAX_ENHANCE))
    buttons = [[(f"+{row['enhancement']} → {short(ITEM_BY_KEY[row['item_key']]['name'], 20)}",
                 f"enhance:{row['item_key']}")]
               for row in rows if ITEM_BY_KEY.get(row['item_key'], {}).get('type') == 'gear']
    stone_key, stone_qty = await find_material(user['user_id'], 'stone')
    await update.effective_message.reply_text(
        f"⚗ <b>Enhancement</b>{NL}Enhancement stones available: {stone_qty}{NL}"
        f"Each attempt costs 1 stone and 100 coins and raises the bonus by +1 up to +{MAX_ENHANCE}.",
        parse_mode=ParseMode.HTML, reply_markup=kb(buttons) if buttons else None)


async def enhance_item(user_id: int, item_key: str) -> str:
    import random
    item = ITEM_BY_KEY.get(item_key)
    row = await fetchone("SELECT enhancement FROM inventory WHERE user_id=? AND item_key=?", (user_id, item_key))
    if not item or not row:
        return "You do not own that gear."
    if row['enhancement'] >= MAX_ENHANCE:
        return "That gear is already at maximum enhancement."
    stone_key, _ = await find_material(user_id, 'stone')
    if not stone_key:
        return "You need an enhancement stone. Buy one from /shop."
    if not await atomic_spend(user_id, 'coins', 100):
        return "You need 100 coins."
    if not await take_inventory(user_id, stone_key, 1):
        return "You need an enhancement stone."
    chance = max(0.35, 0.95 - row['enhancement'] * 0.06)
    if random.random() <= chance:
        await execute("UPDATE inventory SET enhancement=enhancement+1 WHERE user_id=? AND item_key=?",
                      (user_id, item_key))
        await execute("UPDATE users SET enhancements=enhancements+1 WHERE user_id=?", (user_id,))
        return f"Success! {item['name']} is now +{row['enhancement'] + 1}."
    return "The enhancement failed and the stone was consumed."


async def craft_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{short(ITEM_BY_KEY[r['output']]['name'], 24)} · {num(r['coins'])}🪙", f"craft:{r['key']}")]
            for r in RECIPES[:16] if r['output'] in ITEM_BY_KEY]
    await update.effective_message.reply_text(
        "🔨 <b>Forge</b>" + NL + "Tap a recipe to craft it from materials and coins.",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def craft_recipe(user_id: int, recipe_key: str) -> str:
    recipe = next((r for r in RECIPES if r['key'] == recipe_key), None)
    if not recipe:
        return "Unknown recipe."
    for need in recipe['materials']:
        stock = await fetchone("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?",
                               (user_id, need['key']))
        effect = ITEM_BY_KEY.get(need['key'], {}).get('effect', '')
        available = stock['quantity'] if stock else 0
        if available < need['qty']:
            if effect in ('stone', 'catalyst'):
                _, available = await find_material(user_id, effect)
            if available < need['qty']:
                name = ITEM_BY_KEY.get(need['key'], {}).get('name', need['key'])
                return f"You need {need['qty']}× {name}."
    if not await atomic_spend(user_id, 'coins', recipe['coins']):
        return "Not enough coins."
    for need in recipe['materials']:
        if not await take_inventory(user_id, need['key'], need['qty']):
            effect = ITEM_BY_KEY.get(need['key'], {}).get('effect', '')
            if effect in ('stone', 'catalyst'):
                alt, _ = await find_material(user_id, effect)
                if alt:
                    await take_inventory(user_id, alt, need['qty'])
    await add_inventory(user_id, recipe['output'], 1)
    return f"Crafted {ITEM_BY_KEY[recipe['output']]['name']}."


def register(app):
    for name, fn in [("inv", inventory_cmd), ("inventory", inventory_cmd), ("bag", inventory_cmd),
                     ("gear", gear_cmd), ("equip", gear_cmd), ("unequip", unequip_menu),
                     ("shop", shop_cmd), ("forge", craft_cmd), ("craft", craft_cmd),
                     ("enhance", enhance_cmd)]:
        app.add_handler(CommandHandler(name, fn))
