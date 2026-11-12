"""Gacha banners, player market, currency."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import BANNERS, BANNER_BY_KEY, CHARACTER_BY_KEY, ITEM_BY_KEY
from database import fetchone, fetchall, execute, add_inventory, give_character
from handlers.common import guard
from utils import NL, DIV, esc, fmt_num, kb, short
import random

async def summon_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    args = context.args or []
    banner_key = args[0] if args else "standard"
    banner = BANNER_BY_KEY.get(banner_key)
    if not banner:
        lines = ["✨ <b>Banners</b>", DIV]
        for b in BANNERS:
            lines.append(f"/summon {b['key']} — {esc(b['name'])}")
        await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)
        return
    cost = banner.get("cost_single", 50)
    if user["gems"] < cost:
        await update.effective_message.reply_text(f"Need {cost} gems.")
        return
    await execute("UPDATE players SET gems = gems - ? WHERE user_id=?", (cost, user["user_id"]))
    pool = banner.get("pool", [])
    if not pool:
        await update.effective_message.reply_text("Banner pool empty.")
        return
    char_key = random.choice(pool)
    char = CHARACTER_BY_KEY.get(char_key, {})
    new = not await fetchone("SELECT 1 FROM owned_characters WHERE user_id=? AND char_key=?", (user["user_id"], char_key))
    await give_character(user["user_id"], char_key)
    msg = f"You summoned {esc(char.get('name', char_key))}!"
    if new:
        msg += " (New!)"
    await update.effective_message.reply_text(msg)

async def market_cmd(update, context):
    rows = await fetchall("SELECT id, seller_id, item_key, quantity, price, listed_at FROM market_listings ORDER BY listed_at DESC LIMIT 20")
    lines = ["🏪 <b>Market</b>", DIV]
    for r in rows:
        item = ITEM_BY_KEY.get(r["item_key"], {})
        lines.append(f"ID {r['id']}: {esc(item.get('name', r['item_key']))} x{r['quantity']} — {fmt_num(r['price'])} coins")
    if len(lines) == 2:
        lines.append("No listings.")
    lines.append(f"{NL}Use /marketbuy <id>")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def market_sell_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    args = context.args or []
    if len(args) < 3:
        await update.effective_message.reply_text("Usage: /marketsell <item_key> <quantity> <price>")
        return
    key, qty, price = args[0], int(args[1]), int(args[2])
    inv = await fetchone("SELECT quantity FROM inventory WHERE user_id=? AND item_key=?", (user["user_id"], key))
    if not inv or inv["quantity"] < qty:
        await update.effective_message.reply_text("Not enough items.")
        return
    await execute("UPDATE inventory SET quantity = quantity - ? WHERE user_id=? AND item_key=?", (qty, user["user_id"], key))
    await execute("INSERT INTO market_listings(seller_id, item_key, quantity, price) VALUES(?,?,?,?)", (user["user_id"], key, qty, price))
    await update.effective_message.reply_text("Listed.")

async def market_buy_cmd(update, context):
    buyer = await guard(update)
    if not buyer:
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text("Usage: /marketbuy <listing_id>")
        return
    lid = int(args[0])
    row = await fetchone("SELECT * FROM market_listings WHERE id=?", (lid,))
    if not row:
        await update.effective_message.reply_text("Listing not found.")
        return
    if row["seller_id"] == buyer["user_id"]:
        await update.effective_message.reply_text("You cannot buy your own listing.")
        return
    if buyer["coins"] < row["price"]:
        await update.effective_message.reply_text("Not enough coins.")
        return
    fee = int(row["price"] * 0.05)
    payout = row["price"] - fee
    await execute("UPDATE players SET coins = coins - ? WHERE user_id=?", (row["price"], buyer["user_id"]))
    await execute("UPDATE players SET coins = coins + ? WHERE user_id=?", (payout, row["seller_id"]))
    await add_inventory(buyer["user_id"], row["item_key"], row["quantity"])
    await execute("DELETE FROM market_listings WHERE id=?", (lid,))
    await update.effective_message.reply_text("Purchased.")

def register(app):
    app.add_handler(CommandHandler("summon", summon_cmd))
    app.add_handler(CommandHandler("market", market_cmd))
    app.add_handler(CommandHandler("marketsell", market_sell_cmd))
    app.add_handler(CommandHandler("marketbuy", market_buy_cmd))
