"""Single callback router: every inline button in the bot resolves here."""
from __future__ import annotations
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from data_catalog import (BANNERS, BANNER_BY_KEY, CHARACTER_BY_KEY, CATALOG_COUNTS, DUNGEONS,
                          ENEMY_BY_KEY, ITEM_BY_KEY, NPC_BY_KEY, REGIONS, SERIES, SERIES_BY_ID)
from database import ensure_user, execute, fetchall, fetchone
from handlers import characters, clan_pets_social as social, combat_world as combat
from handlers import crown_admin, gacha_market as market, inventory_gear as inv, skills as skills_mod
from handlers.common import clan_of, guard, send_or_edit
from utils import NL, DIV, esc, kb, num, short


async def _menu_home(query, user):
    text = (
        f"🏯 <b>Anime RPG</b> · {esc(user['display_name'])}" + NL + DIV + NL +
        f"Level {user['level']} · 🪙 {num(user['coins'])} · 💎 {num(user['gems'])} · ⚡ {user['energy']}/10" + NL +
        f"Region {esc(user['region'])}" + NL + DIV + NL +
        f"Content loaded: {CATALOG_COUNTS['characters_total']} characters, "
        f"{CATALOG_COUNTS['characters_by_world']}" + NL +
        "Pick a system below."
    )
    rows = [
        [("🪪 Profile", "menu:profile"), ("👥 Characters", "menu:chars")],
        [("⚔ Hunt", "menu:hunt"), ("🏰 Dungeon", "menu:dungeon")],
        [("🎒 Inventory", "menu:inv"), ("🛒 Shop", "menu:shop")],
        [("🔮 Summon", "banner:list"), ("⚖ Market", "market:list")],
        [("🐾 Pets", "menu:pets"), ("🏰 Clan", "menu:clan")],
        [("📖 Skills", "menu:skills"), ("📚 Catalog", "menu:catalog")],
    ]
    return await send_or_edit(query, text, kb(rows))


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user = await ensure_user(query.from_user)
    if user['banned']:
        return await send_or_edit(query, "This account is suspended.")

    raw = query.data or ""
    parts = raw.split(":")
    action = parts[0]
    uid = user['user_id']

    def arg(i, default=""):
        return parts[i] if len(parts) > i else default

    # ---------------------------------------------------------------- menus
    if action == "menu":
        key = arg(1)
        if key == "home":
            return await _menu_home(query, user)
        if key == "profile":
            return await characters.profile_cmd(update, context)
        if key == "chars":
            rows = [[(f"{esc(s['name'])} · {s['requested_count']}", f"series:{s['id']}")] for s in SERIES]
            return await send_or_edit(query, "⚡ <b>Choose a universe</b>", kb(rows))
        if key == "hunt":
            return await send_or_edit(
                query, "⚔ <b>Hunt</b>" + NL + "One energy per fight. Choose an activity:",
                kb([[("⚔ Hunt", "hunt:go"), ("🗺 Explore", "hunt:explore")],
                    [("🏰 Dungeon", "menu:dungeon"), ("👑 Boss", "menu:boss")]]))
        if key == "dungeon":
            rows = [[(f"{esc(d['name'])} · {d['difficulty']}", f"dungeon:{d['key']}")] for d in DUNGEONS[:15]]
            return await send_or_edit(query, "🏰 <b>Dungeons</b>" + NL + "Two energy per run.", kb(rows))
        if key == "boss":
            from data_catalog import BOSSES
            rows = [[(f"{esc(b['name'])} · {b['rank']}", f"bossfight:{b['key']}")] for b in BOSSES[:12]]
            return await send_or_edit(query, "👑 <b>Boss summons</b>" + NL + "Three energy per attempt.", kb(rows))
        if key == "inv" and parts[2:3] == ["forge"]:
            return await inv.craft_cmd(update, context)
        if key == "inv":
            return await send_or_edit(
                query, "🎒 <b>Inventory</b>" + NL + f"🪙 {num(user['coins'])} · 💎 {num(user['gems'])}",
                kb([[("📦 View bag", "bag:list")],
                    [("🛡 Gear", "gear:menu"), ("⚗ Enhance", "enhance:menu")],
                    [("🔨 Forge", "menu:inv:forge")]]))
        if key == "shop":
            rows = [[(f"{esc(s['name'])}", f"shop:{s['id']}:0")] for s in SERIES]
            rows.append([("🧪 Universal", "shop:all:0")])
            return await send_or_edit(query, "🛒 <b>Shop</b>" + NL + f"Coins 🪙 {num(user['coins'])}", kb(rows))
        if key == "pets":
            return await social.pets_cmd(update, context)
        if key == "clan":
            return await social.clan_cmd(update, context)
        if key == "skills":
            return await skills_mod.skills_cmd(update, context)
        if key == "catalog":
            return await crown_admin.catalog_cmd(update, context)
        return await _menu_home(query, user)

    # ------------------------------------------------------------- universe
    if action == "series":
        if arg(1) == "back":
            rows = [[(f"{esc(s['name'])} · {s['requested_count']}", f"series:{s['id']}")] for s in SERIES]
            return await send_or_edit(query, "⚡ <b>Choose a universe</b>", kb(rows))
        from data_catalog import CHARACTERS_BY_SERIES, RANK_ICON, RANKS
        series_id = arg(1)
        if series_id not in SERIES_BY_ID:
            return await send_or_edit(query, "Unknown universe.")
        chars = CHARACTERS_BY_SERIES[series_id]
        rows = [[(f"{RANK_ICON[r]} Rank {r} · {sum(1 for c in chars if c['rank'] == r)}",
                  f"ranklist:{series_id}:{r}")] for r in RANKS]
        rows.append([("⬅ Universes", "menu:chars")])
        series = SERIES_BY_ID[series_id]
        return await send_or_edit(
            query, f"<b>{esc(series['name'])}</b>" + NL +
                   f"Theme: {esc(series['theme'])} · {len(chars)} characters", kb(rows))

    if action == "ranklist":
        series_id, rank = arg(1), arg(2)
        page = int(arg(3, "0") or 0)
        from data_catalog import CHARACTERS_BY_SERIES
        chars = [c for c in CHARACTERS_BY_SERIES.get(series_id, []) if c['rank'] == rank]
        per_page = 10
        total = max(1, (len(chars) + per_page - 1) // per_page)
        page = max(0, min(page, total - 1))
        shown = chars[page * per_page:(page + 1) * per_page]
        rows = [[(f"{short(c['name'], 30)}", f"char:{c['key']}")] for c in shown]
        nav = []
        if page > 0:
            nav.append(("⬅", f"ranklist:{series_id}:{rank}:{page - 1}"))
        if page + 1 < total:
            nav.append(("➡", f"ranklist:{series_id}:{rank}:{page + 1}"))
        if nav:
            rows.append(nav)
        rows.append([("⬅ Ranks", f"series:{series_id}")])
        return await send_or_edit(
            query, f"<b>Rank {rank}</b> · page {page + 1}/{total} · {len(chars)} characters", kb(rows))

    if action == "randchar":
        import random
        from data_catalog import CHARACTERS_BY_SERIES
        chars = CHARACTERS_BY_SERIES.get(arg(1), [])
        if not chars:
            return await send_or_edit(query, "Unknown universe.")
        char = random.choice(chars)
        owned = await fetchone("SELECT * FROM owned_characters WHERE user_id=? AND char_key=?",
                               (uid, char['key']))
        return await send_or_edit(query, characters.character_card(char, owned),
                                  kb(characters.character_buttons(char, owned)))

    if action == "char":
        char = CHARACTER_BY_KEY.get(arg(1))
        if not char:
            return await send_or_edit(query, "Unknown character.")
        owned = await fetchone("SELECT * FROM owned_characters WHERE user_id=? AND char_key=?",
                               (uid, char['key']))
        text = characters.character_card(char, owned)
        markup = kb(characters.character_buttons(char, owned))
        art = await fetchone("SELECT file_id FROM custom_art WHERE entity_key=?", (char['key'],))
        if art and query.message:
            await query.message.reply_photo(art['file_id'], caption=text, parse_mode=ParseMode.HTML,
                                            reply_markup=markup)
            return None
        return await send_or_edit(query, text, markup)

    if action == "charskills":
        char = CHARACTER_BY_KEY.get(arg(1))
        if not char:
            return await send_or_edit(query, "Unknown character.")
        from data_catalog import SKILL_BY_KEY
        lines = [f"📚 <b>{esc(char['name'])} skills</b>", DIV]
        for key in char['skills']:
            skill = SKILL_BY_KEY.get(key)
            if skill:
                lines.append(f"• {esc(skill['name'])} — {skill['type']} · power {skill['power']} · MP {skill['cost']}")
        return await send_or_edit(query, NL.join(lines), kb([[("⬅ Back", f"char:{char['key']}")]]))

    if action == "equipchar":
        char_key = arg(1)
        owned = await fetchone("SELECT 1 FROM owned_characters WHERE user_id=? AND char_key=?", (uid, char_key))
        if not owned:
            return await send_or_edit(query, "You do not own that character.")
        await execute("UPDATE users SET active_char=? WHERE user_id=?", (char_key, uid))
        return await send_or_edit(query, f"⚡ {esc(CHARACTER_BY_KEY[char_key]['name'])} is now active.")

    if action == "team":
        slot, char_key = int(arg(1, "1")), arg(2)
        owned = await fetchone("SELECT 1 FROM owned_characters WHERE user_id=? AND char_key=?", (uid, char_key))
        if not owned:
            return await send_or_edit(query, "You do not own that character.")
        await execute("INSERT INTO team(user_id,slot,char_key) VALUES(?,?,?) "
                      "ON CONFLICT(user_id,slot) DO UPDATE SET char_key=excluded.char_key",
                      (uid, slot, char_key))
        return await send_or_edit(query, f"Squad slot {slot} updated.")

    if action == "alloc":
        column = arg(1)
        if column not in ("str_stat", "agi", "int_stat", "vit", "luk"):
            return await send_or_edit(query, "Invalid stat.")
        _, changed = await execute(
            f"UPDATE users SET {column}={column}+1, stat_points=stat_points-1 "
            "WHERE user_id=? AND stat_points>0", (uid,))
        return await send_or_edit(query, "Point allocated." if changed else "No stat points available.")

    if action == "levelup":
        return await send_or_edit(query, await characters.do_levelup(uid, arg(1)))

    if action == "starup":
        char_key = arg(1)
        owned = await fetchone("SELECT * FROM owned_characters WHERE user_id=? AND char_key=?", (uid, char_key))
        if not owned:
            return await send_or_edit(query, "You do not own that character.")
        if owned['stars'] >= 6:
            return await send_or_edit(query, "That character is already at six stars.")
        if owned['shards'] < 20:
            return await send_or_edit(query, f"You need 20 shards (you have {owned['shards']}).")
        await execute("UPDATE owned_characters SET shards=shards-20, stars=stars+1 "
                      "WHERE user_id=? AND char_key=?", (uid, char_key))
        return await send_or_edit(query, f"⭐ Raised to {owned['stars'] + 1} stars.")

    # --------------------------------------------------------------- combat
    if action in ("hunt", "fight"):
        sub = arg(1)
        if action == "hunt":
            if sub == "explore":
                context.args = ["explore"]
            else:
                context.args = []
            return await combat.hunt_cmd(update, context)
        if sub == "again":
            context.args = []
            return await combat.hunt_cmd(update, context)
        note = await combat.do_battle_action(uid, sub)
        battle = await combat.get_battle(uid)
        if not battle:
            return await send_or_edit(query, note, kb([[("🏠 Menu", "menu:home")]]))
        enemy = ENEMY_BY_KEY.get(battle['enemy_key'], {})
        return await send_or_edit(query, combat.battle_card(battle, enemy.get('name', 'Enemy'), note),
                                  combat.battle_buttons(battle))

    if action == "dungeon":
        note = await combat.enter_dungeon(uid, arg(1))
        battle = await combat.get_battle(uid)
        if not battle:
            return await send_or_edit(query, note, kb([[("🏠 Menu", "menu:home")]]))
        enemy = ENEMY_BY_KEY.get(battle['enemy_key'], {})
        return await send_or_edit(query, combat.battle_card(battle, enemy.get('name', 'Enemy'), note),
                                  combat.battle_buttons(battle))

    if action == "bossfight":
        note = await combat.start_boss(uid, arg(1))
        battle = await combat.get_battle(uid)
        if not battle:
            return await send_or_edit(query, note, kb([[("🏠 Menu", "menu:home")]]))
        enemy = ENEMY_BY_KEY.get(battle['enemy_key'], {})
        return await send_or_edit(query, combat.battle_card(battle, enemy.get('name', 'Enemy'), note),
                                  combat.battle_buttons(battle))

    if action == "world":
        if arg(1) == "back":
            rows = [[(f"{esc(s['name'])}", f"world:{s['id']}")] for s in SERIES]
            return await send_or_edit(query, "🗺 <b>Choose a world</b>", kb(rows))
        return await combat.region_list(query.message, arg(1))

    if action == "travel":
        region_key = arg(1)
        region = next((r for r in REGIONS if r['key'] == region_key), None)
        if not region:
            return await send_or_edit(query, "Unknown region.")
        await execute("UPDATE users SET region=? WHERE user_id=?", (region['name'], uid))
        return await send_or_edit(
            query, f"🗺 Traveled to <b>{esc(region['name'])}</b>" + NL + esc(region['description']),
            kb([[("⚔ Hunt here", "hunt:go"), ("🗺 Regions", f"world:{region['series']}")]]))

    if action == "npc":
        return await send_or_edit(query, await combat.talk_to_npc(uid, arg(1)))

    # ---------------------------------------------------------------- gacha
    if action == "banner":
        if arg(1) in ("list", ""):
            rows = [[(f"{esc(b['name'])}", f"banner:{b['key']}")] for b in BANNERS]
            return await send_or_edit(query, f"🔮 <b>Banners</b>{NL}Gems 💎 {num(user['gems'])}", kb(rows))
        return await market.banner_panel(query.message, uid, arg(1))

    if action == "gacha":
        result = await market.do_pull(uid, arg(1), int(arg(2, "1") or 1))
        banner = BANNER_BY_KEY.get(arg(1))
        rows = [[(f"1× · {banner['single_cost']} 💎", f"gacha:{banner['key']}:1"),
                 (f"10× · {banner['ten_cost']} 💎", f"gacha:{banner['key']}:10")]] if banner else []
        rows.append([("⬅ Banners", "banner:list")])
        return await send_or_edit(query, result, kb(rows))

    # --------------------------------------------------------------- market
    if action == "market":
        sub = arg(1)
        if sub == "sell":
            return await market.market_sell_cmd(update, context)
        if sub == "mine":
            return await market.my_listings(query.message, uid)
        return await market.market_cmd(update, context)

    if action == "marketsell":
        text, markup = market.price_menu(arg(1))
        return await send_or_edit(query, text, markup)

    if action == "marketprice":
        return await send_or_edit(query, await market.list_item(uid, arg(1), int(arg(2, "0") or 0)),
                                  kb([[("⚖ Market", "market:list")]]))

    if action == "marketbuy":
        return await send_or_edit(query, await market.buy_listing(uid, int(arg(1, "0") or 0)),
                                  kb([[("⚖ Market", "market:list")]]))

    if action == "marketcancel":
        return await send_or_edit(query, await market.cancel_listing(uid, int(arg(1, "0") or 0)),
                                  kb([[("📦 My listings", "market:mine")]]))

    # ---------------------------------------------------------------- items
    if action == "shop" and arg(1) != "root":
        title, rows = inv.shop_page(arg(1), int(arg(2, "0") or 0))
        return await send_or_edit(query, title, kb(rows))
    if action == "shop":
        rows = [[(f"{esc(s['name'])}", f"shop:{s['id']}:0")] for s in SERIES]
        rows.append([("🧪 Universal", "shop:all:0")])
        return await send_or_edit(query, "🛒 <b>Shop</b>", kb(rows))
    if action == "buy":
        return await send_or_edit(query, await inv.buy_item(uid, arg(1)), kb([[("🛒 Shop", "shop:root:0")]]))
    if action == "equip":
        return await send_or_edit(query, await inv.equip_gear(uid, arg(1)), kb([[("🛡 Gear", "gear:menu")]]))
    if action == "unequip":
        item_key = arg(1)
        await execute("UPDATE inventory SET equipped_slot=NULL WHERE user_id=? AND item_key=?", (uid, item_key))
        return await send_or_edit(query, "Unequipped.", kb([[("🛡 Gear", "gear:menu")]]))
    if action == "bag":
        return await inv.inventory_cmd(update, context)
    if action == "gear":
        return await inv.gear_cmd(update, context)
    if action == "enhance":
        if arg(1) == "menu":
            return await inv.enhance_cmd(update, context)
        return await send_or_edit(query, await inv.enhance_item(uid, arg(1)),
                                  kb([[("⚗ Enhance", "enhance:menu")]]))
    if action == "craft":
        return await send_or_edit(query, await inv.craft_recipe(uid, arg(1)), kb([[("🔨 Forge", "menu:inv")]]))

    # --------------------------------------------------------------- skills
    if action == "learn":
        if arg(1) == "menu":
            return await skills_mod.learn_cmd(update, context)
        return await send_or_edit(query, await skills_mod.learn_skill(uid, arg(1)),
                                  kb([[("📖 Skills", "menu:skills")]]))
    if action == "skillequip":
        return await skills_mod.skill_equip_cmd(update, context)
    if action == "skillset":
        slot, skill_key = int(arg(1, "0") or 0), arg(2)
        await execute("UPDATE owned_skills SET slot=NULL WHERE user_id=? AND slot=?", (uid, slot))
        await execute("UPDATE owned_skills SET slot=? WHERE user_id=? AND skill_key=?", (slot, uid, skill_key))
        return await send_or_edit(query, f"Skill equipped to slot {slot + 1}.")

    # ---------------------------------------------------------------- clans
    if action == "clandonate":
        return await send_or_edit(query, await social.donate(uid, int(arg(1, "0") or 0)),
                                  kb([[("🏰 Clan", "menu:clan")]]))
    if action == "clanleave":
        if arg(1) == "yes":
            return await send_or_edit(query, await social.leave_clan(uid), kb([[("🏠 Menu", "menu:home")]]))
        return await social.leave_prompt(query.message, uid)
    if action == "clanpromote":
        return await send_or_edit(query, await social.promote(uid, int(arg(1, "0") or 0)),
                                  kb([[("🏰 Clan", "menu:clan")]]))
    if action == "clandisband":
        if arg(1) == "yes":
            return await send_or_edit(query, await social.disband(uid), kb([[("🏠 Menu", "menu:home")]]))
        return await social.disband_prompt(query.message, uid)
    if action == "clan":
        if arg(1) == "leave":
            return await social.leave_prompt(query.message, uid)
        if arg(1) == "promote":
            return await social.promote_prompt(query.message, uid)
        if arg(1) == "disband":
            return await social.disband_prompt(query.message, uid)
        return await social.clan_cmd(update, context)

    # ----------------------------------------------------------------- pets
    if action == "petsummon":
        return await send_or_edit(query, await social.summon_pet(uid), kb([[("🐾 Pets", "menu:pets")]]))
    if action == "petequip":
        return await send_or_edit(query, await social.equip_pet(uid, arg(1)), kb([[("🐾 Pets", "menu:pets")]]))
    if action == "petfeed":
        return await send_or_edit(query, await social.feed_pet(uid, arg(1)), kb([[("🐾 Pets", "menu:pets")]]))

    # ------------------------------------------------------- titles & tops
    if action == "title":
        return await send_or_edit(query, await social.set_title(uid, arg(1)), kb([[("🎖 Titles", "menu:home")]]))
    if action == "top":
        field = arg(1)
        if field not in ("level", "coins", "gems", "pve_wins", "pvp_wins", "boss_wins"):
            return await send_or_edit(query, "Unknown leaderboard.")
        rows = await fetchall(f"SELECT display_name, {field} value FROM users WHERE banned=0 "
                              f"ORDER BY {field} DESC LIMIT 15")
        lines = [f"🏆 <b>Top {field}</b>", DIV]
        for i, row in enumerate(rows, 1):
            lines.append(f"{i}. {esc(row['display_name'])} — {num(row['value'])}")
        return await send_or_edit(query, NL.join(lines), kb([[("⬅ Leaderboards", "menu:home")]]))
    if action == "settings":
        await execute("UPDATE users SET notifications=1-notifications WHERE user_id=?", (uid,))
        fresh = await fetchone("SELECT notifications FROM users WHERE user_id=?", (uid,))
        return await send_or_edit(
            query, f"⚙ Notifications {'on' if fresh['notifications'] else 'off'}.",
            kb([[("⚙ Settings", "menu:home")]]))

    return await send_or_edit(query, "That button is no longer valid. Use /start.", kb([[("🏠 Menu", "menu:home")]]))


def register(app):
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(callback))
