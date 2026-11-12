"""Inventory, equipment, enhancement, forge, shop."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import (
    ITEM_BY_KEY, WEAPON_BY_KEY, ARMOR_BY_KEY, RECIPES, RECIPE_BY_KEY,
)
from database import fetchone, fetchall, execute, add_inventory, take_inventory
from handlers.common import guard
from utils import NL, DIV, esc, fmt_num

async def inventory_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall("SELECT item_key, quantity FROM inventory WHERE user_id=? AND quantity>0", (user["user_id"],))
    lines = ["🎒 <b>Inventory</b>", DIV]
    for r in rows:
        item = ITEM_BY_KEY.get(r["item_key"], {})
        lines.append(f"{esc(item.get('name', r['item_key']))} x{r['quantity']}")
    if len(lines) == 2:
        lines.append("Empty.")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def equip_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text("Usage: /equip <weapon_key|armor_key>")
        return
    key = args[0]
    w = WEAPON_BY_KEY.get(key)
    a = ARMOR_BY_KEY.get(key)
    if not w and not a:
        await update.effective_message.reply_text("Unknown gear key.")
        return
    if w:
        await execute("UPDATE players SET equipped_weapon=? WHERE user_id=?", (key, user["user_id"]))
        await update.effective_message.reply_text(f"Equipped weapon: {esc(w['name'])}")
    else:
        await execute("UPDATE players SET equipped_armor=? WHERE user_id=?", (key, user["user_id"]))
        await update.effective_message.reply_text(f"Equipped armor: {esc(a['name'])}")

async def enhance_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text("Usage: /enhance <gear_key>")
        return
    key = args[0]
    item = WEAPON_BY_KEY.get(key) or ARMOR_BY_KEY.get(key)
    if not item:
        await update.effective_message.reply_text("Unknown gear.")
        return
    row = await fetchone("SELECT enhancement FROM gear_enhancements WHERE user_id=? AND gear_key=?", (user["user_id"], key))
    level = row["enhancement"] if row else 0
    if level >= 10:
        await update.effective_message.reply_text("Max enhancement (+10).")
        return
    cost = 100 + level * 50
    stone = "enhance_stone"
    has_stone = await fetchone("SELECT quantity FROM inventory WHERE user_id=? AND item_key=? AND quantity>0", (user["user_id"], stone))
    if user["coins"] < cost or not has_stone:
        await update.effective_message.reply_text(f"Need {cost} coins and 1 enhancement stone.")
        return
    import random
    chance = max(0.35, 0.95 - 0.06 * level)
    if random.random() > chance:
        await execute("UPDATE players SET coins = coins - ? WHERE user_id=?", (cost, user["user_id"]))
        await take_inventory(user["user_id"], stone, 1)
        await update.effective_message.reply_text("Enhancement failed.")
        return
    await execute("UPDATE players SET coins = coins - ? WHERE user_id=?", (cost, user["user_id"]))
    await take_inventory(user["user_id"], stone, 1)
    await execute(
        "INSERT INTO gear_enhancements(user_id, gear_key, enhancement) VALUES(?,?,?) ON CONFLICT(user_id, gear_key) DO UPDATE SET enhancement=excluded.enhancement+1",
        (user["user_id"], key, level + 1),
    )
    await update.effective_message.reply_text(f"{esc(item['name'])} is now +{level+1}")

async def forge_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    args = context.args or []
    if len(args) < 1:
        lines = ["⚒ <b>Forge recipes</b>", DIV]
        for r in RECIPES[:18]:
            lines.append(f"/forge {r['key']} — {esc(r['name'])}")
        await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)
        return
    recipe = RECIPE_BY_KEY.get(args[0])
    if not recipe:
        await update.effective_message.reply_text("Unknown recipe.")
        return
    for mat_key, qty in recipe.get("materials", {}).items():
        if not await take_inventory(user["user_id"], mat_key, qty):
            await update.effective_message.reply_text(f"Missing materials for {recipe['name']}.")
            return
    result_key = recipe["result_key"]
    result = WEAPON_BY_KEY.get(result_key) or ARMOR_BY_KEY.get(result_key) or ITEM_BY_KEY.get(result_key)
    await add_inventory(user["user_id"], result_key, recipe.get("quantity", 1))
    await update.effective_message.reply_text(f"Forged: {esc(result['name'] if result else result_key)}")

async def shop_cmd(update, context):
    lines = ["🛒 <b>Shop</b>", DIV]
    for item in list(ITEM_BY_KEY.values())[:20]:
        price = item.get("buy_price", 0)
        if price > 0:
            lines.append(f"/buy {item['key']} — {esc(item['name'])} · {fmt_num(price)} coins")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def buy_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text("Usage: /buy <item_key> [quantity]")
        return
    key = args[0]
    qty = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
    item = ITEM_BY_KEY.get(key)
    if not item:
        await update.effective_message.reply_text("Unknown item.")
        return
    price = item.get("buy_price", 0) * qty
    if user["coins"] < price:
        await update.effective_message.reply_text("Not enough coins.")
        return
    await execute("UPDATE players SET coins = coins - ? WHERE user_id=?", (price, user["user_id"]))
    await add_inventory(user["user_id"], key, qty)
    await update.effective_message.reply_text(f"Bought {esc(item['name'])} x{qty}")

def register(app):
    app.add_handler(CommandHandler("inventory", inventory_cmd))
    app.add_handler(CommandHandler("equip", equip_cmd))
    app.add_handler(CommandHandler("enhance", enhance_cmd))
    app.add_handler(CommandHandler("forge", forge_cmd))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("buy", buy_cmd))
