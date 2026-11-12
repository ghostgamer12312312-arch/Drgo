"""Gacha banners with pity, plus the player-to-player market."""
from __future__ import annotations
import random
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import (BANNERS, BANNER_BY_KEY, CHARACTER_BY_KEY, CHARACTERS_BY_SERIES,
                          ITEM_BY_KEY, RANKS, RARITY, SERIES, SERIES_BY_ID)
from database import execute, fetchone, fetchall, add_inventory, atomic_spend, take_inventory
from handlers.common import guard
from utils import NL, DIV, esc, kb, num, rank_tag, short

DEFAULT_BANNER = "standard"
MARKET_FEE = 0.05
PRICE_TIERS = [100, 500, 2500, 10000]


def rank_pool(banner: dict) -> dict:
    pool = {rank: [] for rank in RANKS}
    if banner['series'] == 'all':
        for rank in RANKS:
            pool[rank] = [c['key'] for c in CHARACTER_BY_KEY.values() if c['rank'] == rank]
    else:
        for char in CHARACTERS_BY_SERIES.get(banner['series'], []):
            pool[char['rank']].append(char['key'])
    return pool


def banner_card(banner: dict, pity: int) -> str:
    rates = banner.get('rates', {'Z': 1.0, 'S': 5.0, 'A': 18.0, 'B': 34.0, 'E': 42.0})
    lines = [
        f"🔮 <b>{esc(banner['name'])}</b>",
        DIV,
        f"Featured: {esc(', '.join(CHARACTER_BY_KEY[k]['name'] for k in banner['featured'][:3]) or 'none')}",
        f"Mythic pity: <b>{pity}/{banner['mythic_pity']}</b>",
        DIV,
        "Rates: " + " · ".join(f"{rank_tag(rank)} {rate}%" for rank, rate in rates.items()),
        DIV,
        f"Single: {banner['single_cost']} 💎 · Ten pull: {banner['ten_cost']} 💎",
    ]
    return NL.join(lines)


async def banner_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{esc(b['name'])}", f"banner:{b['key']}")] for b in BANNERS]
    await update.effective_message.reply_text(
        f"🔮 <b>Summon banners</b>{NL}Gems 💎 {num(user['gems'])}{NL}Pick a banner:",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def banner_panel(message, user_id: int, banner_key: str):
    banner = BANNER_BY_KEY.get(banner_key)
    if not banner:
        return await message.reply_text("Unknown banner.")
    pity_row = await fetchone("SELECT pulls FROM gacha_pity WHERE user_id=? AND banner_key=?",
                              (user_id, banner_key))
    pity = pity_row['pulls'] if pity_row else 0
    rows = [[(f"1× · {banner['single_cost']} 💎", f"gacha:{banner_key}:1"),
             (f"10× · {banner['ten_cost']} 💎", f"gacha:{banner_key}:10")],
            [("📜 Banner list", "banner:list"), ("🪪 Profile", "menu:profile")]]
    await message.reply_text(banner_card(banner, pity), parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def do_pull(user_id: int, banner_key: str, count: int) -> str:
    banner = BANNER_BY_KEY.get(banner_key)
    if not banner:
        return "Unknown banner."
    if count not in (1, 10):
        return "Choose a single or ten pull."
    cost = banner['single_cost'] if count == 1 else banner['ten_cost']
    if not await atomic_spend(user_id, 'gems', cost):
        return f"Not enough gems. That pull costs {cost} 💎."
    pool = rank_pool(banner)
    rates = banner.get('rates', {'Z': 1.0, 'S': 5.0, 'A': 18.0, 'B': 34.0, 'E': 42.0})
    pity_row = await fetchone("SELECT pulls FROM gacha_pity WHERE user_id=? AND banner_key=?",
                              (user_id, banner_key))
    pity = pity_row['pulls'] if pity_row else 0
    results, gained_new = [], 0
    for _ in range(count):
        pity += 1
        force = pity >= banner['mythic_pity']
        if force:
            rank = 'Z'
            pity = 0
        else:
            rank = random.choices(list(rates.keys()), weights=list(rates.values()))[0]
        candidates = pool.get(rank) or pool.get('S') or list(CHARACTER_BY_KEY)
        # Featured characters are twice as likely inside their own rank bracket.
        weighted = []
        for key in candidates:
            weighted.extend([key] * (2 if key in banner['featured'] else 1))
        char_key = random.choice(weighted)
        char = CHARACTER_BY_KEY[char_key]
        owned = await fetchone("SELECT 1 FROM owned_characters WHERE user_id=? AND char_key=?",
                               (user_id, char_key))
        if owned:
            await execute("UPDATE owned_characters SET shards=shards+1 WHERE user_id=? AND char_key=?",
                          (user_id, char_key))
            results.append(f"{rank_tag(rank)} {esc(char['name'])} → +1 shard")
        else:
            await execute("INSERT INTO owned_characters(user_id, char_key) VALUES(?,?)", (user_id, char_key))
            gained_new += 1
            results.append(f"{rank_tag(rank)} <b>{esc(char['name'])}</b> — NEW")
    await execute(
        "INSERT INTO gacha_pity(user_id,banner_key,pulls) VALUES(?,?,?) "
        "ON CONFLICT(user_id,banner_key) DO UPDATE SET pulls=excluded.pulls",
        (user_id, banner_key, pity))
    await execute("UPDATE users SET summons=summons+? WHERE user_id=?", (count, user_id))
    header = f"🎉 <b>Summon results</b> · {count} pull(s) · {gained_new} new character(s)"
    return header + NL + DIV + NL + NL.join(results)


async def market_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    listings = await fetchall(
        "SELECT * FROM market_listings WHERE active=1 ORDER BY listing_id DESC LIMIT 12")
    if not listings:
        return await update.effective_message.reply_text(
            "⚖ The market has no active listings. Use /market_sell to create the first one.")
    lines = ["⚖ <b>Player market</b>", DIV]
    buttons = []
    for row in listings:
        item = ITEM_BY_KEY.get(row['item_key'], {'name': row['item_key']})
        lines.append(f"#{row['listing_id']} {esc(item['name'])} ×{row['quantity']} · {num(row['price'])} 🪙")
        buttons.append([(f"Buy #{row['listing_id']} · {num(row['price'])}🪙", f"marketbuy:{row['listing_id']}")])
    buttons.append([("🏷 Sell an item", "market:sell"), ("📦 My listings", "market:mine")])
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML, reply_markup=kb(buttons))


async def market_sell_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall("SELECT item_key, quantity FROM inventory WHERE user_id=? AND quantity>0", (user['user_id'],))
    buttons = [[(f"{short(ITEM_BY_KEY[r['item_key']]['name'], 24)} ×{r['quantity']}", f"marketsell:{r['item_key']}")]
               for r in rows if r['item_key'] in ITEM_BY_KEY][:20]
    await update.effective_message.reply_text(
        f"🏷 <b>Sell on the market</b>{NL}Pick an item, then choose a price tier.",
        parse_mode=ParseMode.HTML, reply_markup=kb(buttons) if buttons else None)


def price_menu(item_key: str):
    rows = [[(f"{num(price)} 🪙", f"marketprice:{item_key}:{price}")] for price in PRICE_TIERS]
    rows.append([("⬅ Back", "market:list")])
    item = ITEM_BY_KEY.get(item_key, {'name': item_key})
    return f"🏷 Listing <b>{esc(item['name'])}</b>{NL}Choose a price (5% market fee applies on sale):", kb(rows)


async def list_item(user_id: int, item_key: str, price: int) -> str:
    if price not in PRICE_TIERS:
        return "Invalid price tier."
    if not await take_inventory(user_id, item_key, 1):
        return "You do not have that item."
    await execute("INSERT INTO market_listings(seller_id,item_key,quantity,price) VALUES(?,?,1,?)",
                  (user_id, item_key, price))
    return f"Listed {ITEM_BY_KEY[item_key]['name']} for {num(price)} coins."


async def buy_listing(user_id: int, listing_id: int) -> str:
    listing = await fetchone("SELECT * FROM market_listings WHERE listing_id=? AND active=1", (listing_id,))
    if not listing:
        return "That listing is gone."
    if listing['seller_id'] == user_id:
        return "You cannot buy your own listing."
    if not await atomic_spend(user_id, 'coins', listing['price']):
        return "Not enough coins."
    changed = await execute("UPDATE market_listings SET active=0 WHERE listing_id=? AND active=1", (listing_id,))
    if changed[1] != 1:
        await execute("UPDATE users SET coins=coins+? WHERE user_id=?", (listing['price'], user_id))
        return "Someone else bought it first; your coins were refunded."
    payout = int(listing['price'] * (1 - MARKET_FEE))
    await execute("UPDATE users SET coins=coins+?, market_trades=market_trades+1 WHERE user_id=?",
                  (payout, listing['seller_id']))
    await add_inventory(user_id, listing['item_key'], listing['quantity'])
    await execute("UPDATE users SET market_trades=market_trades+1 WHERE user_id=?", (user_id,))
    return f"Bought {ITEM_BY_KEY[listing['item_key']]['name']} for {num(listing['price'])} coins."


async def my_listings(message, user_id: int):
    rows = await fetchall(
        "SELECT * FROM market_listings WHERE seller_id=? AND active=1 ORDER BY listing_id DESC", (user_id,))
    if not rows:
        return await message.reply_text("You have no active listings.")
    lines = ["📦 <b>Your listings</b>", DIV]
    buttons = []
    for row in rows:
        lines.append(f"#{row['listing_id']} {esc(ITEM_BY_KEY[row['item_key']]['name'])} · {num(row['price'])} 🪙")
        buttons.append([(f"Cancel #{row['listing_id']}", f"marketcancel:{row['listing_id']}")])
    await message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML, reply_markup=kb(buttons))


async def cancel_listing(user_id: int, listing_id: int) -> str:
    row = await fetchone("SELECT * FROM market_listings WHERE listing_id=? AND seller_id=? AND active=1",
                         (listing_id, user_id))
    if not row:
        return "Listing not found."
    await execute("UPDATE market_listings SET active=0 WHERE listing_id=?", (listing_id,))
    await add_inventory(user_id, row['item_key'], row['quantity'])
    return "Listing cancelled and the item returned to your bag."


def register(app):
    for name, fn in [("gacha", banner_cmd), ("banner", banner_cmd), ("pull", banner_cmd),
                     ("summon", banner_cmd), ("market", market_cmd), ("market_sell", market_sell_cmd),
                     ("market_buy", market_cmd), ("market_cancel", market_cmd)]:
        app.add_handler(CommandHandler(name, fn))
