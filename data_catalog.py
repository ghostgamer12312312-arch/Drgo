"""Large deterministic original anime-inspired game catalog.

The catalog uses original characters, names, abilities and lore rather than
reproducing official franchise character rosters. Each requested theme keeps
the requested roster size. Forms are separate collectible character records.
"""
from __future__ import annotations
import hashlib

SERIES = [
    {"id":"ki","name":"Ki Frontier","theme":"energy warriors","requested_count":110},
    {"id":"shinobi","name":"Shadow Shinobi","theme":"ninja clans","requested_count":80},
    {"id":"tempest","name":"Tempest Realms","theme":"fantasy storm world","requested_count":70},
    {"id":"curse","name":"Cursed Arts","theme":"cursed techniques","requested_count":80},
    {"id":"spirit","name":"Spirit Court","theme":"soul blades","requested_count":70},
]
SERIES_BY_ID={s['id']:s for s in SERIES}
RANKS=["Z","S","A","B","E"]
RARITY={"Z":"Mythic","S":"Legendary","A":"Epic","B":"Rare","E":"Common"}
RANK_ICON={"Z":"🔴","S":"🟡","A":"🟣","B":"🔵","E":"⚪"}
PREFIXES={
    "ki":["Kael","Rai","Tova","Mira","Daren","Sora","Vey","Niko","Asha","Rokan","Tali","Zev","Luma","Kori","Bren","Yara","Oren","Sumi","Jax","Eira","Mako","Riven","Sela","Torin","Nara","Kellan","Vira","Dax","Liora","Haru"],
    "shinobi":["Akio","Ren","Miko","Taro","Yuna","Kaito","Hina","Sora","Daichi","Mei","Riku","Aya","Kenji","Nori","Emi","Takeshi","Aiko","Ryo","Mina","Jun","Kohana","Shiro","Ranmaru","Natsuki","Itsuki","Kiyomi","Tsubasa","Rei","Masato","Hoshi"],
    "tempest":["Aurel","Sylvi","Thalen","Morrow","Ilyra","Bram","Eldin","Vexa","Nym","Caelum","Orla","Tarin","Mirel","Fen","Lazuli","Oryn","Maelis","Kest","Runa","Valk","Solenne","Perrin","Ivara","Beryl","Eamon","Zorya","Rell","Calyx","Mirael","Tovin"],
    "curse":["Yori","Kenta","Misato","Arata","Nobu","Keiko","Shun","Makiya","Satsuki","Junpei","Kuro","Natsuo","Hiro","Fuyu","Akane","Rin","Soma","Tetsu","Kanna","Yasu","Mio","Satoru","Kirie","Takumi","Eiji","Noa","Kiyo","Retsu","Yume","Daigo"],
    "spirit":["Ichiro","Kaede","Rukon","Mizuki","Kenshin","Tsubame","Hotaru","Yasuo","Kohana","Shiori","Masaru","Nanao","Kaito","Arare","Hibiki","Kazane","Akito","Yori","Suzume","Ranmaru","Tsukiko","Haru","Kiyone","Isamu","Fumiko","Retsu","Aoi","Takeru","Suzu","Reika"],
}
SURNAMES=["Veyra","Kestrel","Moonfall","Ashborne","Rin","Kurogane","Windmere","Solari","Dawncrest","Mizuno","Hoshino","Stormveil","Emberlyn","Frostvale","Nightbloom","Tideborn","Starling","Ironwood","Ravenna","Cloudstep","Sable","Aster","Thorn","Brightwater","Sundara","Vale","Morino","Kisaragi","Rook","Evermist"]
FORMS={
    "ki":["Base","Rising Aura","Radiant State","Celestial Drive","Limit Break"],
    "shinobi":["Base","Veil Step","Sage Mantle","Astral Mark"],
    "tempest":["Base","Awakened Core","Tempest Crown"],
    "curse":["Base","Resonant Curse","Domain Form","Eclipse State"],
    "spirit":["Base","Released Blade","Final Release","Spirit Ascendant"],
}
ELEMENTS={
    "ki":["Ki","Solar","Gravity","Pulse","Dragon"],
    "shinobi":["Wind","Flame","Water","Earth","Lightning","Shadow"],
    "tempest":["Storm","Nature","Frost","Stone","Void","Arcane"],
    "curse":["Curse","Blood","Sound","Barrier","Soul","Lightning"],
    "spirit":["Spirit","Steel","Ice","Ash","Light","Shadow"],
}
TRAITS=["Fearless","Tactical","Patient","Fierce","Focused","Unyielding","Keen","Lucky","Resolute","Cunning","Protective","Swift","Calm","Ambitious","Adaptable","Vigilant"]
ABILITY_LEFT=["Rising","Silent","Crimson","Azure","Celestial","Iron","Phantom","Storm","Dawn","Eclipse","Radiant","Hidden","Ancient","Feral","Astral","Searing","Moonlit","Thunder","Void","Golden"]
ABILITY_RIGHT=["Wave","Fist","Lance","Guard","Burst","Crescent","Step","Nova","Current","Edge","Pulse","Roar","Mirage","Barrier","Comet","Spiral","Bloom","Rift","Dance","Beacon"]
RANK_STATS={"Z":(220,56,30,28),"S":(185,47,25,24),"A":(155,38,21,20),"B":(128,30,17,16),"E":(105,23,14,13)}

def _n(seed): return int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8],"big")
def _rank(i): return ["Z","S","A","B","E"][(i*7 + i//5)%5]
def _series_chars(series):
    sid=series['id']; target=series['requested_count']; names=[]
    for i in range(30):
        first=PREFIXES[sid][i%len(PREFIXES[sid])]
        last=SURNAMES[(i*7+_n(sid+str(i))%len(SURNAMES))%len(SURNAMES)]
        names.append(f"{first} {last}")
    out=[]; base_index=0
    while len(out)<target:
        base=names[base_index%len(names)]
        form_list=FORMS[sid]
        form_index=base_index//len(names)
        if form_index>=len(form_list): form_index=len(form_list)-1
        if base_index>=len(names)*len(form_list):
            form_index=1+(base_index% (len(form_list)-1))
        form=form_list[form_index]
        rank=_rank(base_index+_n(sid+base+form)%11)
        ident=f"{sid}_{len(out)+1:03d}"
        hp,atk,defense,speed=RANK_STATS[rank]
        seed=sid+base+form
        name=base if form=="Base" else f"{base} · {form}"
        ability=f"{ABILITY_LEFT[_n(seed+'l')%20]} {ABILITY_RIGHT[_n(seed+'r')%20]}"
        out.append({"key":ident,"name":name,"base_name":base,"form":form,"form_index":form_index,
          "forms":form_list,"series":sid,"series_name":series['name'],"rank":rank,"rarity":RARITY[rank],
          "element":ELEMENTS[sid][_n(seed+'el')%len(ELEMENTS[sid])],"trait":TRAITS[_n(seed+'tr')%len(TRAITS)],
          "ability":ability,"unique":f"{TRAITS[_n(seed+'un')%len(TRAITS)]} resonance: bonus {(_n(seed+'n')%7)+3}% {['attack','defense','speed','ultimate charge'][_n(seed+'b')%4]}",
          "hp":hp+_n(seed+'hp')%24,"atk":atk+_n(seed+'at')%8,"def":defense+_n(seed+'df')%6,"spd":speed+_n(seed+'sp')%5,
          "skills":[f"{sid}_sk_{(_n(seed+str(j))%20)+1:02d}" for j in range(3)],
          "fusion":"" if len(out)%4 else f"{sid}_fusion_{len(out)+1:03d}","stars":5+(rank=='Z')})
        base_index+=1
    return out

CHARACTERS=[c for s in SERIES for c in _series_chars(s)]
CHARACTER_BY_KEY={c['key']:c for c in CHARACTERS}
CHARACTERS_BY_SERIES={s['id']:[c for c in CHARACTERS if c['series']==s['id']] for s in SERIES}

SKILL_KINDS=["damage","damage","damage","heal","buff","debuff","damage","dot","damage","damage","shield","damage","heal","damage","buff","damage","debuff","damage","damage","ultimate"]
def _skills(s):
    names=[f"{ABILITY_LEFT[(i+_n(s['id']+str(i)))%20]} {ABILITY_RIGHT[(i*3+_n(s['id']+'x'+str(i)))%20]}" for i in range(20)]
    rows=[]
    for i,name in enumerate(names):
        key=f"{s['id']}_sk_{i+1:02d}"; kind=SKILL_KINDS[i]
        rows.append({"key":key,"name":name,"series":s['id'],"series_name":s['name'],"rank":_rank(i),"type":kind,
          "power":round(1.25+(_n(key)%150)/100,2) if kind in ('damage','dot','ultimate') else round(.12+(_n(key)%22)/100,2),
          "cost":8+_n(key+'c')%25,"cooldown":1+_n(key+'cd')%3,"description":f"Original {s['theme']} technique with {kind} effect."})
    return rows
SKILLS=[x for s in SERIES for x in _skills(s)]
SKILL_BY_KEY={x['key']:x for x in SKILLS}

WEAPON_TYPES=["Blade","Spear","Staff","Gauntlets","Bow","Twin Daggers","Hammer","Whip","Lance","Greatblade","Chakram","Saber","War Fan","Crossbow","Short Sword","Orb","Polearm","Scythe","Claw","Tonfa"]
ARMOR_TYPES=["Battle Coat","Reinforced Vest","Scale Mail","Spirit Robe","Scout Mantle","Guardian Plate","Warden Cloak","Ritual Wrap","Tempest Suit","Duelist Jacket","Aegis Armor","Shadow Garb","Trail Armor","Knight Mail","Rune Robe","Storm Shell","Sentinel Harness","Moonweave","Iron Mantle","Phoenix Guard"]
ITEM_PREFIX={"ki":"Aura","shinobi":"Hidden","tempest":"Tempest","curse":"Cursed","spirit":"Spirit"}

def _gear(series,slot,i):
    sid=series['id']; rank=_rank(i*3+_n(sid+slot+str(i))%8); base,atk0,def0,spd0=RANK_STATS[rank]
    typ=(WEAPON_TYPES if slot=='Weapon' else ARMOR_TYPES)[i]
    key=f"{sid}_{'wp' if slot=='Weapon' else 'ar'}_{i+1:02d}"
    return {"key":key,"name":f"{ITEM_PREFIX[sid]} {typ}","series":sid,"series_name":series['name'],"type":"gear","slot":slot,"rank":rank,"rarity":RARITY[rank],
      "atk":(4+i%8 if slot=='Weapon' else 0)+(atk0//9 if slot=='Weapon' else 0),"def":(5+i%7 if slot=='Armor' else 0)+(def0//8 if slot=='Armor' else 0),
      "spd":(i%5 if slot=='Weapon' else 0),"price":100+_n(key)%4500,"description":f"Original {series['theme']} {slot.lower()}.","enhancement_max":10}
GEAR=[_gear(s,slot,i) for s in SERIES for slot in ('Weapon','Armor') for i in range(20)]

CONSUMABLE_NAMES=["Minor Recovery Tonic","Greater Recovery Tonic","Energy Draught","Stamina Meal","Focus Incense","Battle Ration","Experience Manual","Revival Feather","Lucky Charm","Fortune Coin","Barrier Salve","Critical Oil","Speed Elixir","Guard Pill","Ultimate Charge Orb","Skill Scroll","Enhancement Stone","Pet Food","Pet Egg","Elite Key","Boss Key","Summon Ticket","Dragon Relic","Crafting Dust","Forge Catalyst","Clan Donation Token","Dungeon Map","Travel Pass","Trait Reroll","Skill Manual","Healing Seed","Energy Capsule","Shard Bundle","Market Voucher","Quest Seal"]
ITEM_TYPES=["consumable","consumable","consumable","consumable","consumable","consumable","consumable","consumable","consumable","consumable","consumable","consumable","consumable","consumable","consumable","material","material","material","material","material","material","material","material","material","material","material","material","material","material","material","consumable","consumable","material","material","material"]
ITEM_EFFECTS=["heal","heal","energy","energy","buff","xp","xp","revive","luck","coins","shield","crit","speed","defense","ultimate","skill_scroll","stone","pet_food","pet_egg","elite_key","boss_key","ticket","relic","dust","catalyst","token","map","travel","trait_reroll","skill_manual","heal","energy","shards","voucher","quest"]
ITEM_BY_KEY={}
ITEMS=[]
for s in SERIES:
    for i,(name,kind,effect) in enumerate(zip(CONSUMABLE_NAMES,ITEM_TYPES,ITEM_EFFECTS)):
        key=f"{s['id']}_it_{i+1:02d}"
        row={"key":key,"name":f"{ITEM_PREFIX[s['id']]} {name}","series":s['id'],"series_name":s['name'],"type":kind,"effect":effect,
             "amount":30+(_n(key)%160),"rank":_rank(i),"rarity":RARITY[_rank(i)],"price":50+_n(key+'p')%1800,
             "description":f"A useful {s['theme']} item."}
        ITEMS.append(row); ITEM_BY_KEY[key]=row
for g in GEAR: ITEMS.append(g); ITEM_BY_KEY[g['key']]=g
UNIVERSAL_ITEMS=[{"key":k,"name":n,"type":"material","effect":e,"amount":0,"price":p,"rank":"A","rarity":"Epic","series":"all","series_name":"Universal","description":d}
 for k,n,e,p,d in [("coins","Coins","currency",0,"Common currency."),("gems","Gems","currency",0,"Premium game currency."),("dragon_balls","Dragon Relic Orbs","wish",0,"Seven relic orbs grant one wish."),("scrap","Gear Scrap","catalyst",30,"Forge material."),("food","Pet Food","pet_food",120,"Feed companions."),("enhance_stone","Universal Enhancement Stone","stone",260,"Raises gear enhancement."),("skill_scroll","Universal Skill Scroll","skill_scroll",900,"Teaches one skill.")]]

PET_NAMES={"ki":["Comet Fox","Ember Cub","Orbit Moth","Sunscale Drake","Pulse Hare","Meteor Pup","Aura Finch","Nova Tortoise"],"shinobi":["Whisper Hound","Paper Crane","Shadow Cat","Mist Toad","Bamboo Fox","Lantern Crow","River Otter","Stone Beetle"],"tempest":["Cloud Wyrm","Moss Sprite","Gale Lynx","Frost Fawn","Thunder Mite","Moon Moth","Rune Owl","Dew Dragon"],"curse":["Echo Imp","Grim Lantern","Threadling","Cinder Wisp","Mirror Crow","Redcap Spirit","Hollow Pup","Bell Phantom"],"spirit":["Blade Finch","Soul Koi","Ash Moth","Moon Hound","Silver Carp","Lotus Wisp","Lantern Fox","Wind Crane"]}
PETS=[]
for s in SERIES:
    for i,name in enumerate(PET_NAMES[s['id']]):
        rank=_rank(i*3)
        PETS.append({"key":f"{s['id']}_pet_{i+1:02d}","name":name,"series":s['id'],"series_name":s['name'],"rank":rank,"rarity":RARITY[rank],
          "bonus_type":["atk","def","speed","hp","crit","coins","xp","ultimate"][i],"bonus":3+i%5,"description":f"Original {s['theme']} companion."})
PET_BY_KEY={p['key']:p for p in PETS}

ENEMY_TYPES=["Rogue Scout","Wild Brute","Veil Adept","Ruin Guardian","Cinder Stalker","Wandering Duelist","Night Wraith","Iron Sentinel","Feral Beast","Storm Marauder","Lost Initiate","Abyss Runner","Crystal Hound","Silent Archer","Gate Keeper"]
BOSS_TYPES=["The Ashen Regent","Crown of the Deep","The Hollow Colossus","Tempest Sovereign","The Glass Tyrant","Warden of Embers","The Nameless Herald","Eclipse Beast"]
ENEMIES=[]; BOSSES=[]
for s in SERIES:
    sid=s['id']; base_rank_stats=RANK_STATS
    for i,name in enumerate(ENEMY_TYPES):
        rank=["E","E","B","B","A","B","A","A","B","S","E","B","A","B","S"][i]
        hp,atk,df,spd=base_rank_stats[rank]
        ENEMIES.append({"key":f"{sid}_en_{i+1:02d}","name":f"{ITEM_PREFIX[sid]} {name}","series":sid,"rank":rank,"boss":False,
          "hp":hp+30+i*4,"atk":atk,"def":df,"xp":25+atk*3,"coins":18+atk*2,"gems":0,"drops":[]})
    for i,name in enumerate(BOSS_TYPES):
        rank="Z" if i in (0,3,6) else "S"; hp,atk,df,spd=base_rank_stats[rank]
        BOSSES.append({"key":f"{sid}_boss_{i+1:02d}","name":f"{ITEM_PREFIX[sid]} {name}","series":sid,"rank":rank,"boss":True,
          "hp":hp*5,"atk":atk*2,"def":df*2,"xp":500+atk*15,"coins":350+atk*12,"gems":15+i*3,"drops":[f"{sid}_it_22",f"{sid}_it_23"]})
ENEMIES_ALL=ENEMIES+BOSSES
ENEMY_BY_KEY={e['key']:e for e in ENEMIES_ALL}

NPC_ROLES=["Field Mentor","Wandering Merchant","Forge Keeper","Guild Registrar","Village Healer","Map Archivist","Scout Captain","Story Guide","Pet Keeper","Quest Steward"]
NPCS=[]
for s in SERIES:
    for i,role in enumerate(NPC_ROLES):
        NPCS.append({"key":f"{s['id']}_npc_{i+1:02d}","name":f"{ITEM_PREFIX[s['id']]} {role}","series":s['id'],"role":role,
          "dialogue":["Every step forward teaches a lesson.","Prepare well before entering the dungeon.","Your companions grow alongside you.","The market rewards careful planning."][i%4],
          "quest":f"{s['id']}_quest_{i+1:02d}","reward_coins":100+i*40,"reward_xp":50+i*20})

REGION_BASE=["Home Outpost","Training Meadow","Whispering Wood","Sunken Quarter","Frostline Ridge","Ashen Basin","Cloudstep Pass","Ancient Gate"]
REGIONS=[]
for s in SERIES:
    for i,name in enumerate(REGION_BASE):
        REGIONS.append({"key":f"{s['id']}_region_{i+1:02d}","name":f"{ITEM_PREFIX[s['id']]} {name}","series":s['id'],"tier":i+1,
          "description":f"A tier {i+1} region in the {s['name']} world.","enemy_key":f"{s['id']}_en_{i%15+1:02d}","boss_key":f"{s['id']}_boss_{i%8+1:02d}"})

DUNGEONS=[]
for s in SERIES:
    for i in range(6):
        DUNGEONS.append({"key":f"{s['id']}_dungeon_{i+1:02d}","name":f"{ITEM_PREFIX[s['id']]} Trial {i+1}","series":s['id'],"difficulty":["Normal","Hard","Nightmare"][i%3],"floors":3+i%3,
          "boss_key":f"{s['id']}_boss_{i%8+1:02d}","reward_coins":250+i*100,"reward_xp":180+i*80})

BANNERS=[{"key":"standard","name":"World Summon","series":"all","single_cost":50,"ten_cost":450,"mythic_pity":90,"featured":[] }]
for s in SERIES:
    BANNERS.append({"key":f"banner_{s['id']}","name":f"{s['name']} Featured Banner","series":s['id'],"single_cost":55,"ten_cost":500,"mythic_pity":80,
      "featured":[c['key'] for c in CHARACTERS_BY_SERIES[s['id']] if c['rank']=='Z'][:3]})
BANNER_BY_KEY={b['key']:b for b in BANNERS}

QUESTS=[
 {"key":"daily_hunt","name":"Win 3 hunts","metric":"hunt_wins","target":3,"coins":250,"gems":5,"xp":100},
 {"key":"daily_explore","name":"Explore twice","metric":"explores","target":2,"coins":180,"gems":3,"xp":80},
 {"key":"daily_gacha","name":"Make one summon","metric":"summons","target":1,"coins":150,"gems":0,"xp":60},
 {"key":"weekly_boss","name":"Defeat a boss","metric":"boss_wins","target":1,"coins":700,"gems":15,"xp":300},
 {"key":"weekly_dungeon","name":"Clear a dungeon","metric":"dungeon_wins","target":1,"coins":500,"gems":10,"xp":250},
]
RECIPES=[]
for s in SERIES:
    for i in range(20):
        gear=next(g for g in GEAR if g['series']==s['id'] and g['slot']==('Weapon' if i<10 else 'Armor') and int(g['key'].split('_')[-1])==(i%10+1))
        RECIPES.append({"key":f"{s['id']}_recipe_{i+1:02d}","output":gear['key'],"materials":[{"key":f"{s['id']}_it_24","qty":3+i%4},{"key":f"{s['id']}_it_17","qty":1+i%2}],"coins":100+i*35})
TITLES=[{"name":name,"criterion":crit,"value":value} for name,crit,value in [
 ("Rookie","level",1),("Hunter","pve_wins",10),("Duelist","pvp_wins",10),("Summoner","summons",25),
 ("Boss Breaker","boss_wins",5),("Dungeon Runner","dungeon_wins",10),("Clan Patron","donations",1000),
 ("Forge Master","enhancements",10),("Market Maker","market_trades",10),("Explorer","explores",25),
 ("Champion","level",50),("Ascendant","level",100),("Unbroken","pve_wins",100),("Gemkeeper","gems",5000),
 ("Wealthy","coins",100000)]]
# ------------------------------------------------------------------ lookups
NPC_BY_KEY={n['key']:n for n in NPCS}
REGION_BY_KEY={r['key']:r for r in REGIONS}
DUNGEON_BY_KEY={d['key']:d for d in DUNGEONS}
RECIPE_BY_KEY={r['key']:r for r in RECIPES}
CHARACTERS_BY_WORLD_COUNT={s['id']:len(CHARACTERS_BY_SERIES[s['id']]) for s in SERIES}

CATALOG_COUNTS={
 "characters_by_world":{s['name']:s['requested_count'] for s in SERIES},
 "characters_total":len(CHARACTERS),"weapons_per_world":20,"armor_per_world":20,"skills_per_world":20,
 "items_per_world":len(CONSUMABLE_NAMES),"npcs_per_world":len(NPC_ROLES),"bosses_per_world":len(BOSS_TYPES),
 "enemies_per_world":len(ENEMY_TYPES),"pets_per_world":8,"regions_per_world":len(REGION_BASE),"dungeons_per_world":6,
}
