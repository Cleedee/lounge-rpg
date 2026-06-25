import random
import logging
from typing import Any

import config
import i18n
from models import (
    Campaign, PlayerStats, SpecialAbilityState, ActiveEffect,
    ToolResult, ALLOWED_TOOLS, KNOWN_LOCATIONS,
)
from database import get_campaign, save_campaign

logger = logging.getLogger("neon_scratch.game_engine")


def get_campaign_state(campaign_id: str) -> Campaign | None:
    raw = get_campaign(campaign_id)
    if raw is None:
        return None
    return Campaign(**raw)


def patch_campaign_state(campaign: Campaign):
    save_campaign(campaign.model_dump())


def roll_die(sides: int) -> int:
    return random.randint(1, sides)


def tool_roll_dice(args: dict, campaign: Campaign) -> dict:
    sides = int(args.get("sides", 20))
    count = int(args.get("count", 1))
    modifier = int(args.get("modifier", 0))
    purpose = str(args.get("purpose", "unknown"))
    stat_bonus_key = args.get("statBonus")

    rolls = [roll_die(sides) for _ in range(count)]
    stat = 0
    if stat_bonus_key and stat_bonus_key in [
        "pawStrength", "agility", "arcane", "stealth"
    ]:
        stat = getattr(campaign.playerStats, stat_bonus_key, 0)

    total = sum(rolls) + modifier + stat

    logger.info("tool=roll-dice sides=%d count=%d modifier=%d stat=%d rolls=%s total=%d purpose=%s",
                sides, count, modifier, stat, rolls, total, purpose)
    return {
        "rolls": rolls,
        "modifier": modifier,
        "statBonus": stat,
        "total": total,
        "purpose": purpose,
    }


def tool_apply_damage(args: dict, campaign: Campaign) -> dict:
    target_type = str(args.get("targetType", "player"))
    raw_damage = int(args.get("amount", args.get("damage", 0)))
    damage_type = str(args.get("damageType", "unknown"))

    if target_type != "player":
        return {"previousHp": 0, "newHp": 0, "damageBlocked": 0, "nineLivesTrigger": False, "isDead": False}

    previous_hp = campaign.playerStats.hp

    if raw_damage < 0:
        new_hp = min(campaign.playerStats.maxHp, previous_hp + abs(raw_damage))
        campaign.playerStats.hp = new_hp
        patch_campaign_state(campaign)
        logger.info("tool=apply-damage healing=%d previousHp=%d newHp=%d", raw_damage, previous_hp, new_hp)
        return {"previousHp": previous_hp, "newHp": new_hp, "damageBlocked": 0, "nineLivesTrigger": False, "isDead": False}

    damage_blocked = 0
    actual_damage = raw_damage

    if campaign.characterClass == "MaineCoonPaladin" and not campaign.specialAbilityState.shieldUsedThisEncounter:
        if actual_damage > 0:
            damage_blocked = min(15, actual_damage)
            actual_damage -= damage_blocked
            campaign.specialAbilityState.shieldUsedThisEncounter = True
            patch_campaign_state(campaign)

    if damage_type == "laser" and "NeonScratchCoat" in campaign.inventory:
        reduction = min(3, actual_damage)
        actual_damage -= reduction
        damage_blocked += reduction

    new_hp = max(0, previous_hp - actual_damage)
    nine_lives_trigger = False

    if new_hp <= 0 and campaign.characterClass == "TabbyWarrior" and not campaign.specialAbilityState.nineLivesUsed:
        new_hp = 1
        nine_lives_trigger = True
        campaign.specialAbilityState.nineLivesUsed = True
        patch_campaign_state(campaign)

    is_dead = new_hp <= 0
    campaign.playerStats.hp = new_hp
    patch_campaign_state(campaign)

    logger.info("tool=apply-damage target=%s raw=%d actual=%d blocked=%d type=%s prevHp=%d newHp=%d lives=%s dead=%s",
                target_type, raw_damage, actual_damage, damage_blocked, damage_type,
                previous_hp, new_hp, nine_lives_trigger, is_dead)
    return {"previousHp": previous_hp, "newHp": new_hp, "damageBlocked": damage_blocked,
            "nineLivesTrigger": nine_lives_trigger, "isDead": is_dead}


def tool_update_inventory(args: dict, campaign: Campaign) -> dict:
    action = str(args.get("action", "add"))
    item = str(args.get("item", ""))
    inventory = list(campaign.inventory)
    gold = campaign.playerStats.gold
    effect_applied = None

    is_credit_chips = "creditchips" in item.lower()

    if action == "add":
        if is_credit_chips:
            import re
            amount = int(args.get("quantity", 10))
            gold += amount
            campaign.playerStats.gold = gold
            patch_campaign_state(campaign)
        elif item not in inventory:
            inventory.append(item)
            campaign.inventory = inventory
            patch_campaign_state(campaign)
    elif action == "remove":
        if is_credit_chips:
            amount = int(args.get("quantity", 0))
            gold = max(0, gold - amount)
            campaign.playerStats.gold = gold
            patch_campaign_state(campaign)
        else:
            inventory = [i for i in inventory if i != item]
            campaign.inventory = inventory
            patch_campaign_state(campaign)
    elif action == "use":
        item_hp_restore = {
            "MysteryCanOfTuna": 40,
            "MediPack": 30,
            "AdvancedMedKit": 60,
            "Advanced Med-Kit": 60,
            "StandardMedKit": 40,
            "Standard Med-Kit": 40,
        }
        restore = item_hp_restore.get(item, 0)
        if restore > 0:
            new_hp = min(campaign.playerStats.maxHp, campaign.playerStats.hp + restore)
            campaign.playerStats.hp = new_hp
            effect_applied = i18n.t("game.effect.applied", f"Restored {restore}hp", hp=restore)
        else:
            item_effects = {
                "AncientCatnip": i18n.t("game.item.AncientCatnip", "Roll 1d6: 1-2 restore 50hp, 3-4 deal 50 damage to random enemy, 5-6 both"),
                "LaserPointerMk2": i18n.t("game.item.LaserPointerMk2", "Stun enemy for 1 turn"),
            }
            effect_applied = item_effects.get(item, i18n.t("game.effect.unknown", "Unknown effect"))
        inventory = [i for i in inventory if i != item]
        campaign.inventory = inventory
        patch_campaign_state(campaign)

    logger.info("tool=update-inventory action=%s item=%s quantity=%s gold=%d inventory_size=%d",
                action, item, args.get("quantity"), gold, len(inventory))
    return {"inventory": inventory, "gold": gold, "effectApplied": effect_applied}


def tool_award_xp(args: dict, campaign: Campaign) -> dict:
    xp = int(args.get("amount", args.get("xp", 0)))
    previous_level = campaign.playerStats.level
    new_xp = campaign.playerStats.xp + xp
    new_level = int(new_xp / config.XP_PER_LEVEL) + 1
    leveled_up = new_level > previous_level

    stat_improved = None
    max_hp_increase = 0

    if leveled_up:
        stats = ["pawStrength", "agility", "arcane", "stealth"]
        stat_improved = random.choice(stats)
        max_hp_increase = 10

    campaign.playerStats.xp = new_xp
    campaign.playerStats.level = new_level
    campaign.playerStats.maxHp += max_hp_increase

    if stat_improved:
        current = getattr(campaign.playerStats, stat_improved)
        setattr(campaign.playerStats, stat_improved, current + 1)

    patch_campaign_state(campaign)
    logger.info("tool=award-xp xp=%d prevLevel=%d newLevel=%d leveledUp=%s statImproved=%s",
                xp, previous_level, new_level, leveled_up, stat_improved)
    return {"previousLevel": previous_level, "newLevel": new_level, "newXp": new_xp,
            "leveledUp": leveled_up, "statImproved": stat_improved}


def resolve_location(raw: str) -> str | None:
    raw = raw.strip()
    if raw in KNOWN_LOCATIONS:
        return raw
    norm = raw.lower().replace(" ", "").replace("-", "").replace("_", "").replace(",", "").replace(".", "").replace("/", "")
    for loc in KNOWN_LOCATIONS:
        if norm == loc.lower():
            return loc
    for loc in KNOWN_LOCATIONS:
        if norm in loc.lower() or loc.lower() in norm:
            return loc
    return None


def tool_update_location(args: dict, campaign: Campaign) -> dict:
    raw = str(args.get("newLocation", args.get("location", ""))).strip()
    new_location = resolve_location(raw) if raw else None

    if not new_location:
        logger.warning("tool=update-location unresolved location='%s'", raw)
        return {"previousLocation": campaign.currentLocation, "newLocation": campaign.currentLocation, "locationDescription": "No change"}

    previous_location = campaign.currentLocation
    campaign.currentLocation = new_location
    patch_campaign_state(campaign)

    descriptions = {loc: i18n.t(f"game.location.{loc}", d) for loc, d in {
        "NeonScratchLounge": "The resistance HQ. Smells of tuna and old leather. Safe.",
        "ChromeAlley": "Rain-slicked alleys, neon graffiti, RoombaCore patrols.",
        "RoombaCoreTower": "The megacorp HQ. 40 floors of brushed steel. Heavily guarded.",
        "NightMarket": "Underground market. Stolen tech and black-market tuna.",
        "SewersOfForgetfulness": "Ancient sewers. Smells terrible. Home to things that rejected society.",
        "IndustrialZone": "Rusted warehouses and fabrication plants. Sector Nine gangs run protection here.",
    }.items()}
    return {"previousLocation": previous_location, "newLocation": new_location,
            "locationDescription": descriptions.get(new_location, new_location)}


def tool_apply_effect(args: dict, campaign: Campaign) -> dict:
    effect = str(args.get("effect", ""))
    duration = int(args.get("turnsRemaining", args.get("duration", 1)))

    active_effects = [
        ActiveEffect(**{"effect": e["effect"] if isinstance(e, dict) else e.effect,
                        "turnsRemaining": (e["turnsRemaining"] if isinstance(e, dict) else e.turnsRemaining) - 1})
        if isinstance(e, dict) else ActiveEffect(effect=e.effect, turnsRemaining=e.turnsRemaining - 1)
        for e in campaign.activeEffects
    ]
    active_effects = [e for e in active_effects if e.turnsRemaining > 0]

    if isinstance(effect, str):
        active_effects.append(ActiveEffect(effect=effect, turnsRemaining=duration))

    campaign.activeEffects = active_effects
    patch_campaign_state(campaign)
    return {"activeEffects": [e.model_dump() for e in active_effects]}


def tool_use_special_ability(args: dict, campaign: Campaign) -> dict:
    ability = str(args.get("abilityName", args.get("ability", "")))

    class_abilities = {
        "TabbyWarrior": "NineLifesPassive",
        "SiameseMage": "LaserFocusSpell",
        "MaineCoonPaladin": "HolyHairballShield",
        "SphinxRogue": "SandstormVanish",
    }

    expected = class_abilities.get(campaign.characterClass)
    if expected != ability:
        raise ValueError(f"Ability {ability} does not match class {campaign.characterClass}")

    mechanical_effect = ""
    cooldown_set = None

    if ability == "SandstormVanish":
        if campaign.specialAbilityState.vanishCooldownTurnsLeft > 0:
            raise ValueError(
                f"SandstormVanish on cooldown: {campaign.specialAbilityState.vanishCooldownTurnsLeft} turns remaining"
            )
        cooldown_set = 3
        campaign.specialAbilityState.vanishCooldownTurnsLeft = cooldown_set
        mechanical_effect = i18n.t("game.ability.SandstormVanish.desc", "All enemy attacks miss this turn. 3-turn cooldown set.")
        patch_campaign_state(campaign)
    elif ability == "LaserFocusSpell":
        new_hp = campaign.playerStats.hp - 10
        if new_hp <= 0:
            raise ValueError("Not enough HP to use LaserFocusSpell (costs 10hp)")
        campaign.playerStats.hp = new_hp
        arc = campaign.playerStats.arcane
        mechanical_effect = i18n.t("game.ability.LaserFocusSpell.desc", f"Spent 10hp. Next attack deals 3x arcane ({arc * 3}) damage.", arc=arc, arc3=arc * 3)
        patch_campaign_state(campaign)
    elif ability == "HolyHairballShield":
        mechanical_effect = i18n.t("game.ability.HolyHairballShield.desc", "Shield active. Will block up to 15 damage on next hit this encounter.")
    elif ability == "NineLifesPassive":
        mechanical_effect = i18n.t("game.ability.NineLifesPassive.desc", "Passive — triggers automatically on death. Cannot be manually activated.")

    return {"abilityUsed": ability, "mechanicalEffect": mechanical_effect, "cooldownSet": cooldown_set}


def tool_update_quest_log(args: dict, campaign: Campaign) -> dict:
    from datetime import datetime, timezone
    entry = str(args.get("entry", ""))
    timestamp = datetime.now(timezone.utc).isoformat()
    quest_log = list(campaign.questLog)
    quest_log.append(f"[{timestamp}] {entry}")
    campaign.questLog = quest_log
    patch_campaign_state(campaign)
    return {"questLog": quest_log}


def run_tool(tool_name: str, tool_args: dict, campaign: Campaign) -> ToolResult:
    if tool_name not in ALLOWED_TOOLS:
        raise ValueError(f"Unknown or disallowed tool: {tool_name}")

    # Always reload fresh campaign state from DB
    fresh = get_campaign_state(campaign.campaignId)
    if fresh is None:
        raise ValueError(f"Campaign {campaign.campaignId} not found")

    # Update our working copy with latest from DB
    # Use __dict__ to preserve nested Pydantic model instances (model_dump() would flatten to dicts)
    for key, value in fresh.__dict__.items():
        setattr(campaign, key, value)

    handlers = {
        "roll-dice": tool_roll_dice,
        "apply-damage": tool_apply_damage,
        "update-inventory": tool_update_inventory,
        "award-xp": tool_award_xp,
        "update-location": tool_update_location,
        "apply-effect": tool_apply_effect,
        "use-special-ability": tool_use_special_ability,
        "update-quest-log": tool_update_quest_log,
    }

    handler = handlers[tool_name]
    result = handler(tool_args, campaign)
    return ToolResult(toolName=tool_name, result=result)
