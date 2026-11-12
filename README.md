# Anime RPG Telegram Bot — large catalog build

A modular, asynchronous Telegram RPG written for Python 3.11+, `python-telegram-bot` v21+
and `aiosqlite`. Every battle is turn-based and manually driven from inline buttons.

## Content shipped

| Content | Per world | Worlds | Total |
|---|---|---|---|
| Characters (every form is a separate entry) | 110 / 80 / 70 / 80 / 70 | 5 | **410** |
| Skills | 20 | 5 | 100 |
| Weapons | 20 | 5 | 100 |
| Armor | 20 | 5 | 100 |
| Items (consumables + materials) | 35 | 5 | 175 + universal |
| Normal enemies | 15 | 5 | 75 |
| Bosses | 8 | 5 | 40 |
| NPCs | 10 | 5 | 50 |
| Regions | 8 | 5 | 40 |
| Dungeons | 6 | 5 | 30 |
| Pets | 8 | 5 | 40 |
| Banners | 1 featured | 5 | 5 + standard |

World sizes: Ki Frontier 110, Shadow Shinobi 80, Tempest Realms 70, Cursed Arts 80,
Spirit Court 70. Names, abilities, gear and lore are original writing rather than
copies of published franchise character lists.

## Feature list

- Auto-registration, ban checks, energy with timed regeneration, daily streaks.
- Character roster browser by world → rank tier → paginated list → detail card.
- Teams, active character, shard-based star upgrades, coin/XP levelling.
- Manual turn-based combat: attack, three skill slots, dodge, ultimate, MP recovery, flee.
- Dungeons with multiple floors and automatic floor advance, boss summons with gems.
- Gear with four slots, enhancement up to +10, forge recipes from materials.
- Shop per world plus universal goods, atomic coin spending on every purchase.
- Gacha banners with per-banner pity counters, featured weighting and shard conversion.
- Player market: list, price tiers, buy, cancel, 5% fee, self-purchase blocking.
- Clans with treasury, level, donations, leader protection (promote or disband) and ranking.
- Pets with summon, equip, feed and passive bonuses that feed into battle stats.
- Leaderboards by level/coins/gems/wins, titles, settings.
- Admin: dashboard, currency/item/character grants, level set, ban/unban, broadcast,
  artwork manager (`/crown`, `/upload`, `/artlist`) using Telegram `file_id`.
- `/catalog` shows the live content counts read from the shipped data.

## Layout

```
main.py                  entry point, /start /help /daily, handler registration
config.py                token, admin ids, database path
database.py              async SQLite schema + guarded CRUD helpers
data_catalog.py          the generated content (characters, gear, items, enemies, …)
game.py                  XP, energy, stats, battle resolution, rewards
utils.py                 formatting helpers (bars, keypads, pagination)
handlers/characters.py   roster, profile, team, level up
handlers/combat_world.py battle cards, dungeons, travel, NPCs, bosses
handlers/inventory_gear.py inventory, gear, shop, enhance, craft
handlers/gacha_market.py banners, pity pulls, player market
handlers/clan_pets_social.py clans, pets, leaderboards, titles, settings
handlers/skills.py       skill learning and slot management
handlers/crown_admin.py  admin tools and artwork manager
handlers/router.py       one callback router for every inline button
run.sh / push_to_github.sh Termux launcher and GitHub publisher
GITHUB_SETUP.md          token + push instructions
```

## Run on Android with Termux

```sh
pkg update -y && pkg upgrade -y
pkg install python git -y
cd anime_rpg_bot
cp .env.example .env
nano .env                # paste BOT_TOKEN and ADMIN_IDS
chmod +x run.sh
./run.sh
```

Optional: `termux-wake-lock` keeps Android from suspending the process during testing.
For a public bot use a real host — phones sleep, and the SQLite file lives on the device.

## Notes and limits

- Content is generated deterministically by `data_catalog.py`; edit the tables there to
  add worlds, characters or gear. Nothing is fetched at runtime.
- Damage numbers, rates and drop chances are tuned for a playable solo economy, not for
  competitive balance. Adjust constants in `game.py` and the handlers.
- Clan raids, PvP duels and trading between players are deliberately not shipped: they
  need anti-abuse design (turn timers, settlement rules) before they are safe to enable.
- Back up `data/rpg.sqlite3`. Never commit it, and never share your bot token.
