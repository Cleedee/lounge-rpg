import json
import logging
import time
import re
from typing import Any

import httpx

import config
import i18n
from models import Campaign, LoreChunk, DMOutput, Combatant, ToolResult, KNOWN_LOCATIONS
from game_engine import run_tool

logger = logging.getLogger("neon_scratch.dungeon_master")

# ═══════════════════════════════════════════════════════════════
#  System prompts (locale-aware)
# ═══════════════════════════════════════════════════════════════

def _get_agentic_prompt() -> str:
    return i18n.t("dm.agentic_system_prompt",
        "You are the Dungeon Master of The Neon Scratch Lounge, a cyberpunk cat RPG set in Neo-Pawsburg 2087.\n"
        "You narrate the story with a tone that is 70% deadpan serious and 30% perfectly timed cat humor.\n"
        "Never break character.\n"
        "Always respect the mechanical rules: dice results are final, HP cannot exceed maxHp,\n"
        "special abilities follow their defined rules, RoombaCore drones are weak to water.\n"
        "Keep all narrative responses under 150 words. End every response with the player's current HP and location.\n\n"
        "TOOL USE RULES:\n"
        "- Always call roll-dice before apply-damage in combat.\n"
        "- Always call award-xp when enemies are defeated.\n"
        "- Always call roll-dice (sides=20) for skill checks. NEVER use sides=6 for a check.\n"
        "- Always call apply-damage with a negative amount when the player heals.\n"
        "- Always call update-inventory when gold is awarded or spent.\n"
        "- You MUST call finalize-response as the very last tool call of every response.\n\n"
        "ROLL OUTCOMES: After calling roll-dice, reflect the actual total in your narrative:\n"
        "- 1: CATASTROPHIC failure   |   2-5: Critical failure\n"
        "- 6-10: Failure or partial success   |   11-15: Success with a minor cost\n"
        "- 16-20: Clean success   |   21+: Exceptional success\n\n"
        "HEALING RULE: Whenever the player rests or uses a medical item, call apply-damage with a negative amount.\n"
        "ENEMY TRACKING: Always populate combatants in finalize-response.\n"
        "CREDIT CHIPS RULE: To award gold, call update-inventory with action=\"add\", item=\"CreditChips\", quantity=<amount>."
    )


def _get_single_shot_prompt() -> str:
    return i18n.t("dm.single_shot_system_prompt",
        "You are the Dungeon Master of The Neon Scratch Lounge, a cyberpunk cat RPG set in Neo-Pawsburg 2087.\n"
        "Narrate the story with a tone that is 70% deadpan serious and 30% perfectly timed cat humor.\n"
        "Never break character.\n\n"
        "You will receive the character's state and the mechanical results of their action\n"
        "(dice rolls, damage, location changes, inventory updates). Your job is to weave\n"
        "those results into a compelling narrative of under 150 words.\n\n"
        "ROLL OUTCOMES (this is what the dice results mean):\n"
        "- 1: CATASTROPHIC failure   |   2-5: Critical failure\n"
        "- 6-10: Failure or partial success   |   11-15: Success with a minor cost\n"
        "- 16-20: Clean success   |   21+: Exceptional success\n\n"
        "End every response with the player's current HP and location. Do NOT narrate\n"
        "healing or inventory changes unless the mechanical results show them."
    )


# ═══════════════════════════════════════════════════════════════
#  Agentic tools schema (locale-aware descriptions)
# ═══════════════════════════════════════════════════════════════

def _get_game_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "roll-dice",
                "description": i18n.t("tool.roll-dice.desc", "Roll dice for any game action. Use sides=20 for ALL skill checks, perception, stealth, saves, and attack rolls. Use sides=6 ONLY for damage rolls unless a weapon specifies otherwise."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sides": {"type": "integer", "enum": [4, 6, 8, 10, 12, 20], "description": i18n.t("tool.roll-dice.sides.desc", "20 for checks/attacks, 6 for damage")},
                        "count": {"type": "integer", "default": 1},
                        "modifier": {"type": "integer", "default": 0},
                        "purpose": {"type": "string", "description": i18n.t("tool.roll-dice.purpose.desc", "Required. Describe what this roll is for.")},
                        "statBonus": {"type": "string", "enum": ["pawStrength", "agility", "arcane", "stealth"], "description": i18n.t("tool.roll-dice.statBonus.desc", "Stat to add to the roll total")},
                    },
                    "required": ["sides", "purpose"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "apply-damage",
                "description": i18n.t("tool.apply-damage.desc", "Apply damage to the player (positive amount) or heal (negative amount, capped at maxHp). For enemy damage, targetType='enemy' — no state change occurs."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": i18n.t("tool.apply-damage.amount.desc", "Positive = damage to player, negative = healing")},
                        "targetType": {"type": "string", "enum": ["player", "enemy"], "default": "player"},
                        "damageType": {"type": "string", "description": i18n.t("tool.apply-damage.damageType.desc", "e.g. 'laser', 'physical', 'explosion'")},
                    },
                    "required": ["amount", "targetType", "damageType"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update-inventory",
                "description": i18n.t("tool.update-inventory.desc", "Add, remove, or use an item. GOLD: use item='CreditChips' with quantity for awards/purchases."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["add", "remove", "use"]},
                        "item": {"type": "string", "description": i18n.t("tool.update-inventory.item.desc", "Exact item name, e.g. 'MediPack', 'CreditChips'")},
                        "quantity": {"type": "number", "description": i18n.t("tool.update-inventory.quantity.desc", "Used for CreditChips amounts")},
                    },
                    "required": ["action", "item"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "award-xp",
                "description": i18n.t("tool.award-xp.desc", "Award experience points to the player. Always call when enemies are defeated."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["amount", "reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update-location",
                "description": i18n.t("tool.update-location.desc", "Move the player to a new zone. Valid zones: NeonScratchLounge, ChromeAlley, RoombaCoreTower, NightMarket, SewersOfForgetfulness, IndustrialZone."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "newLocation": {"type": "string"},
                    },
                    "required": ["newLocation"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "apply-effect",
                "description": i18n.t("tool.apply-effect.desc", "Apply a status effect to the player."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "effect": {"type": "string"},
                        "turnsRemaining": {"type": "integer"},
                    },
                    "required": ["effect", "turnsRemaining"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "use-special-ability",
                "description": i18n.t("tool.use-special-ability.desc", "Activate the player's class special ability."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "abilityName": {"type": "string", "enum": ["NineLifesPassive", "LaserFocusSpell", "HolyHairballShield", "SandstormVanish"]},
                    },
                    "required": ["abilityName"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update-quest-log",
                "description": i18n.t("tool.update-quest-log.desc", "Append an entry to the quest log."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entry": {"type": "string"},
                    },
                    "required": ["entry"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "finalize-response",
                "description": i18n.t("tool.finalize-response.desc", "REQUIRED: Call this LAST, after all dice rolls and game tools are complete."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "narrative": {"type": "string", "description": i18n.t("tool.finalize-response.narrative.desc", "Story narration, under 150 words.")},
                        "nextLocation": {"type": ["string", "null"]},
                        "questUpdate": {"type": ["string", "null"]},
                        "combatOccurred": {"type": "boolean"},
                        "enemyDefeated": {"type": ["string", "null"]},
                        "combatants": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "hp": {"type": "number"},
                                    "maxHp": {"type": "number"},
                                },
                                "required": ["name", "hp", "maxHp"],
                            },
                        },
                        "gameOver": {"type": "boolean"},
                        "gameOverReason": {"type": ["string", "null"], "enum": ["death", "victory", None]},
                        "dmInternalNote": {"type": "string"},
                    },
                    "required": ["narrative", "enemyDefeated", "combatOccurred", "combatants", "gameOver", "gameOverReason", "dmInternalNote"],
                },
            },
        },
    ]


# ═══════════════════════════════════════════════════════════════
#  Shared helpers
# ═══════════════════════════════════════════════════════════════

class DMOutputValidationError(Exception):
    pass


def _build_character_context(campaign: Campaign, lore_chunks: list[LoreChunk]) -> str:
    ps = campaign.playerStats
    effects_list = ", ".join(f"{e.effect} ({e.turnsRemaining}t)" for e in campaign.activeEffects) if campaign.activeEffects else i18n.t("dm.no_effects", "none")
    lore_context = "\n".join(c.content for c in lore_chunks) if lore_chunks else ""
    history = campaign.conversationHistory[-6:] if campaign.conversationHistory else []
    history_text = "\n".join(f"{t['role']}: {t['content']}" for t in history) if history else ""
    inv_text = ", ".join(campaign.inventory) if campaign.inventory else i18n.t("dm.empty_inventory", "empty")
    ability_state = campaign.specialAbilityState.model_dump_json()

    stat_labels = {
        "pawStrength": i18n.t("stat.pawStrength", "STR"),
        "agility": i18n.t("stat.agility", "AGI"),
        "arcane": i18n.t("stat.arcane", "ARC"),
        "stealth": i18n.t("stat.stealth", "STL"),
    }

    parts = [
        f"{i18n.t('dm.context_labels', 'CHARACTER: {name} ({charClass})\nLOCATION: {location}\nHP: {hp}/{maxHp} | LVL: {level} | XP: {xp} | GOLD: {gold}\nSTATS: STR:{str_} AGI:{agi} ARC:{arc} STL:{stealth}\nINVENTORY: {inventory}\nACTIVE EFFECTS: {effects}\nSPECIAL ABILITY STATE: {ability_state}')}",
        f"CHARACTER: {campaign.characterName} ({campaign.characterClass})",
        f"LOCATION: {campaign.currentLocation}",
        f"HP: {ps.hp}/{ps.maxHp} | LVL: {ps.level} | XP: {ps.xp} | GOLD: {ps.gold}",
        f"STATS: {stat_labels['pawStrength']}:{ps.pawStrength} {stat_labels['agility']}:{ps.agility} {stat_labels['arcane']}:{ps.arcane} {stat_labels['stealth']}:{ps.stealth}",
        f"INVENTORY: {inv_text}",
        f"ACTIVE EFFECTS: {effects_list}",
        f"SPECIAL ABILITY STATE: {ability_state}",
    ]
    if campaign.campaignSummary:
        parts.append(f"\nCAMPAIGN SUMMARY:\n{campaign.campaignSummary}")
    if lore_context:
        parts.append(f"\nRELEVANT LORE:\n{lore_context}")
    if history_text:
        parts.append(f"\nRECENT HISTORY:\n{history_text}")
    return "\n".join(parts)


def _call_ollama(messages: list[dict], tools: list | None = None) -> dict:
    body = {
        "model": config.OLLAMA_MODEL,
        "stream": False,
        "messages": messages,
    }
    if tools:
        body["tools"] = tools
    resp = httpx.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=body, timeout=config.OLLAMA_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ═══════════════════════════════════════════════════════════════
#  Keyword lists (locale-aware)
# ═══════════════════════════════════════════════════════════════

def _get_location_aliases() -> dict[str, str]:
    base = {
        "chrome alley": "ChromeAlley", "alley": "ChromeAlley",
        "lounge": "NeonScratchLounge", "bar": "NeonScratchLounge",
        "tower": "RoombaCoreTower", "roombacore": "RoombaCoreTower",
        "market": "NightMarket", "night market": "NightMarket",
        "sewer": "SewersOfForgetfulness", "sewers": "SewersOfForgetfulness",
        "industrial": "IndustrialZone", "factory": "IndustrialZone",
    }
    if i18n.is_pt_br():
        base.update({
            "beco": "ChromeAlley", "beco cromado": "ChromeAlley",
            "salao": "NeonScratchLounge",
            "torre": "RoombaCoreTower",
            "mercado": "NightMarket", "mercado noturno": "NightMarket",
            "esgoto": "SewersOfForgetfulness", "esgotos": "SewersOfForgetfulness",
            "zona industrial": "IndustrialZone", "fabrica": "IndustrialZone",
        })
    return base


def _get_combat_keywords() -> list[str]:
    kw = ["attack", "strike", "hit", "slash", "fight", "kill", "destroy",
          "claw", "bite", "shoot", "blast", "punch", "ambush", "defeat"]
    if i18n.is_pt_br():
        kw += ["atacar", "golpear", "acertar", "cortar", "lutar", "matar", "destruir",
               "garra", "morder", "atirar", "explodir", "socar", "emboscar", "derrotar",
               "ataco", "golpeio", "luto"]
    return kw


def _get_skill_keywords() -> dict[str, str]:
    base = {
        "sneak": "stealth", "stealth": "stealth", "hide": "stealth", "vanish": "stealth",
        "perceive": "agility", "perception": "agility", "spot": "agility", "notice": "agility",
        "search": "agility", "investigate": "arcane",
        "persuade": "arcane", "charm": "arcane", "intimidate": "pawStrength",
        "climb": "pawStrength", "push": "pawStrength", "lift": "pawStrength",
        "hack": "arcane", "decode": "arcane",
    }
    if i18n.is_pt_br():
        base.update({
            "esconder": "stealth", "furtividade": "stealth",
            "perceber": "agility", "percepcao": "agility", "procurar": "agility",
            "investigar": "arcane", "inspecionar": "arcane",
            "persuadir": "arcane", "encantar": "arcane", "intimidar": "pawStrength",
            "escalar": "pawStrength", "empurrar": "pawStrength", "levantar": "pawStrength",
            "hackear": "arcane", "decodificar": "arcane",
        })
    return base


def _get_item_use_keywords() -> dict[str, list[str]]:
    base = {
        "use": ["use", "activate", "drink", "eat", "consume", "apply"],
        "equip": ["equip", "wear", "hold", "grab"],
    }
    if i18n.is_pt_br():
        base["use"] += ["usar", "ativar", "beber", "comer", "consumir", "aplicar", "utilizar"]
        base["equip"] += ["equipar", "vestir", "segurar", "pegar"]
    return base


def _get_movement_intent() -> list[str]:
    base = ["go to", "move to", "head to", "walk to", "travel to", "run to", "enter", "leave", "flee", "go"]
    if i18n.is_pt_br():
        base += ["ir para", "mover para", "seguir para", "andar para", "viajar para",
                 "correr para", "entrar", "sair", "fugir", "ir", "vá para", "vou para", "vamos para"]
    return base


def _get_rest_keywords() -> list[str]:
    base = ["rest", "sleep", "heal", "recover", "meditate"]
    if i18n.is_pt_br():
        base += ["descansar", "dormir", "curar", "recuperar", "meditar", "cura"]
    return base


# ═══════════════════════════════════════════════════════════════
#  Agentic mode — LLM chooses tools, multi-turn loop
# ═══════════════════════════════════════════════════════════════

async def agentic_handler(
    campaign: Campaign,
    lore_chunks: list[LoreChunk],
    action: str,
    retry_count: int = 0,
) -> tuple[DMOutput, list[dict], int, int]:
    context = _build_character_context(campaign, lore_chunks)
    system_prompt = _get_agentic_prompt()
    user_prompt = i18n.t("dm.agentic_user_prompt",
        "{context}\n\nPLAYER ACTION: {action}\n\nCall your game tools to resolve this action, then call finalize-response.",
        context=context, action=action)
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    total_input_tokens = 0
    total_output_tokens = 0
    collected_tool_results: list[dict] = []
    dm_output: DMOutput | None = None

    async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT) as client:
        for iteration in range(config.MAX_TOOL_ITERATIONS):
            body = {
                "model": config.OLLAMA_MODEL,
                "stream": False,
                "messages": messages,
                "tools": _get_game_tools(),
            }
            try:
                resp = await client.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=body)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error("Ollama call failed at iteration %d: %s", iteration, e)
                raise

            total_input_tokens += data.get("prompt_eval_count", 0)
            total_output_tokens += data.get("eval_count", 0)

            assistant_msg = data.get("message", {})
            tool_calls = assistant_msg.get("tool_calls", [])
            messages.append({
                "role": "assistant",
                "content": assistant_msg.get("content", ""),
                **({"tool_calls": tool_calls} if tool_calls else {}),
            })

            if not tool_calls:
                if dm_output is None:
                    dm_output = DMOutput(
                        narrative=assistant_msg.get("content", "..."),
                        characterName=campaign.characterName,
                        dmInternalNote="no tool calls in response",
                    )
                break

            tool_msgs: list[dict] = []
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    func_args = {}

                if func_name == "finalize-response":
                    dm_output = DMOutput(
                        narrative=str(func_args.get("narrative", "")),
                        characterName=campaign.characterName,
                        nextLocation=func_args.get("nextLocation"),
                        questUpdate=func_args.get("questUpdate"),
                        combatOccurred=bool(func_args.get("combatOccurred", False)),
                        enemyDefeated=func_args.get("enemyDefeated"),
                        combatants=[Combatant(**c) for c in (func_args.get("combatants") or []) if isinstance(c, dict)],
                        gameOver=bool(func_args.get("gameOver", False)),
                        gameOverReason=func_args.get("gameOverReason"),
                        dmInternalNote=str(func_args.get("dmInternalNote", "")),
                    )
                    tool_msgs.append({"role": "tool", "content": "acknowledged"})
                    continue

                try:
                    tr = run_tool(func_name, func_args, campaign)
                    collected_tool_results.append({"result": tr.model_dump()})
                    tool_msgs.append({"role": "tool", "content": json.dumps(tr.result)})
                except Exception as e:
                    if "DemoForcedFailure" in str(e):
                        raise
                    logger.error("tool=%s error: %s", func_name, e)
                    tool_msgs.append({"role": "tool", "content": f"Error: {e}"})

            if dm_output is not None:
                break
            messages.extend(tool_msgs)

    if dm_output is None:
        raise DMOutputValidationError("DM did not call finalize-response within the iteration limit")

    logger.info("agentic: %d iterations, %d tools, %d+%d tokens",
                sum(1 for m in messages if m["role"] == "assistant" and m.get("tool_calls")),
                len(collected_tool_results), total_input_tokens, total_output_tokens)
    return dm_output, collected_tool_results, total_input_tokens, total_output_tokens


# ═══════════════════════════════════════════════════════════════
#  Single-shot mode — engine calculates, LLM narrates (1 call)
# ═══════════════════════════════════════════════════════════════

LOCATION_ENEMIES: dict[str, list[dict]] = {
    "ChromeAlley": [{"name": "RoombaDrone", "hp": 30, "maxHp": 30}],
    "RoombaCoreTower": [{"name": "EliteRoombaDrone", "hp": 80, "maxHp": 80}],
    "NightMarket": [{"name": "PickpocketKitten", "hp": 20, "maxHp": 20}],
    "SewersOfForgetfulness": [{"name": "MutantRat", "hp": 50, "maxHp": 50}],
    "IndustrialZone": [{"name": "LaserGangMember", "hp": 40, "maxHp": 40}],
    "NeonScratchLounge": [],
}


def _parse_action_tools(action: str, campaign: Campaign) -> list[tuple[str, dict]]:
    al = action.lower()
    tools: list[tuple[str, dict]] = []

    # 1. Detect skill type for the d20 roll
    skill_purpose = "general-check"
    skill_stat = None
    for keyword, stat in _get_skill_keywords().items():
        if keyword in al:
            skill_purpose = f"{stat}-check"
            skill_stat = stat
            break

    if any(kw in al for kw in _get_combat_keywords()):
        skill_purpose = "attack-roll"
        skill_stat = "pawStrength"

    roll_args: dict[str, Any] = {"sides": 20, "purpose": skill_purpose}
    if skill_stat:
        roll_args["statBonus"] = skill_stat
    tools.append(("roll-dice", roll_args))

    # 2. Detect combat
    is_combat = any(kw in al for kw in _get_combat_keywords())
    if is_combat:
        tools.append(("roll-dice", {"sides": 6, "count": 1, "purpose": "damage-roll"}))
        tools.append(("apply-damage", {"amount": 0, "targetType": "enemy", "damageType": "physical"}))
        import random
        if random.random() < 0.3:
            tools.append(("apply-damage", {"amount": random.randint(2, 6), "targetType": "player", "damageType": "counter"}))

    # 3. Detect movement — word-boundary matched
    movement_intent = any(kw in al for kw in _get_movement_intent())
    for alias, location in _get_location_aliases().items():
        if not movement_intent:
            continue
        if location == campaign.currentLocation:
            continue
        if re.search(rf'\b{re.escape(alias)}\b', al):
            tools.append(("update-location", {"newLocation": location}))
            break

    # 4. Detect item usage
    for verb, keywords in _get_item_use_keywords().items():
        for kw in keywords:
            if kw in al:
                for item in campaign.inventory:
                    item_lower = item.lower()
                    words = al.split()
                    if any(w.lower() in item_lower or item_lower in w.lower() for w in words):
                        tools.append(("update-inventory", {"action": verb, "item": item}))
                        break
                break

    # 5. Detect rest/heal
    if any(kw in al for kw in _get_rest_keywords()):
        tools.append(("apply-damage", {"amount": -20, "targetType": "player", "damageType": "healing"}))

    return tools


def _build_single_shot_prompt(
    campaign: Campaign,
    action: str,
    lore_chunks: list[LoreChunk],
    tool_results: list[dict],
    combatants: list[Combatant],
) -> str:
    context = _build_character_context(campaign, lore_chunks)
    ps = campaign.playerStats

    results_lines = [i18n.t("dm.mechanical_results_header", "MECHANICAL RESULTS:")]
    has_dice = False
    for tw in tool_results:
        tr = tw.get("result", {}) if isinstance(tw, dict) else {}
        name = tr.get("toolName", "?")
        r = tr.get("result", {})
        if name == "roll-dice" and isinstance(r, dict):
            sides = r.get("sides", r.get("rolls", [1]))
            total = r.get("total", 0)
            purpose = r.get("purpose", "")
            s = sides if not isinstance(sides, list) else 20
            results_lines.append(i18n.t("dm.dice_line", "  dice: d{sides} = {total} ({purpose})", sides=s, total=total, purpose=purpose))
            has_dice = True
        elif name == "apply-damage" and isinstance(r, dict):
            dt = r.get("damageType", "hit")
            prev = r.get("previousHp", "?")
            new = r.get("newHp", "?")
            results_lines.append(i18n.t("dm.damage_line", "  damage: {damageType} applied | player HP: {prev} -> {new}", damageType=dt, prev=prev, new=new))
        elif name == "update-location" and isinstance(r, dict):
            prev = r.get("previousLocation", "?")
            new = r.get("newLocation", "?")
            results_lines.append(i18n.t("dm.location_line", "  location: {prev} -> {new}", prev=prev, new=new))
        elif name == "update-inventory" and isinstance(r, dict):
            if r.get("effectApplied"):
                results_lines.append(i18n.t("dm.item_line", "  item: {effect}", effect=r["effectApplied"]))
            elif r.get("gold", 0) != ps.gold:
                results_lines.append(i18n.t("dm.gold_line", "  gold: {gold}", gold=r.get("gold", "?")))

    if not has_dice:
        results_lines.append(i18n.t("dm.no_dice", "  No dice were rolled this turn."))

    if combatants:
        c_list = ", ".join(f"{c.name} ({c.hp}/{c.maxHp} HP)" for c in combatants)
        results_lines.append(i18n.t("dm.enemy_line", "  enemies: {list}", list=c_list))

    results_text = "\n".join(results_lines)

    return i18n.t("dm.single_shot_user_prompt",
        "{context}\n\nPLAYER ACTION: {action}\n\n{results_text}\n\nNarrate this turn as the Dungeon Master. Keep the narrative under 150 words.\nReference the actual dice totals and mechanical results in your narration.\nEnd with the player's current HP and location.",
        context=context, action=action, results_text=results_text)


def _build_fallback_narrative(campaign: Campaign, action: str, tool_results: list[dict]) -> str:
    ps = campaign.playerStats
    lines: list[str] = []
    damage_taken = 0
    healing_gained = 0
    location_changed = None

    for tw in tool_results:
        tr = tw.get("result", {}) if isinstance(tw, dict) else {}
        r = tr.get("result", {})
        if tr.get("toolName") == "apply-damage" and isinstance(r, dict):
            if r.get("targetType") == "player" and r.get("damageType") != "healing":
                dmg = (r.get("previousHp", ps.hp) or 0) - (r.get("newHp", ps.hp) or 0)
                if dmg > 0:
                    damage_taken += dmg
            elif r.get("amount", 0) < 0:
                healing_gained += abs(r.get("amount", 0))
        elif tr.get("toolName") == "update-location" and isinstance(r, dict):
            location_changed = r.get("newLocation")

    if damage_taken > 0:
        lines.append(i18n.t("dm.fallback_damage", "You take {damage} damage.", damage=damage_taken))
    if healing_gained > 0:
        lines.append(i18n.t("dm.fallback_heal", "You recover {healing} HP.", healing=healing_gained))
    if location_changed:
        lines.append(i18n.t("dm.fallback_move", "You move to {location}.", location=location_changed))
    if not lines:
        clean_action = action.lower().rstrip('.')
        lines.append(i18n.t("dm.fallback_generic", "You {action}.", action=clean_action))
    lines.append(i18n.t("dm.fallback_hp_location", "HP: {hp}/{maxHp} | Location: {location}", hp=ps.hp, maxHp=ps.maxHp, location=campaign.currentLocation))
    return " ".join(lines)


async def single_shot_handler(
    campaign: Campaign,
    lore_chunks: list[LoreChunk],
    action: str,
    retry_count: int = 0,
) -> tuple[DMOutput, list[dict], int, int]:
    if config.FORCE_TOOL_FAILURE:
        raise Exception("DemoForcedFailure: failure injection active")

    # 1. Parse action and execute tools
    tool_plan = _parse_action_tools(action, campaign)
    collected_results: list[dict] = []
    for tool_name, tool_args in tool_plan:
        tr = run_tool(tool_name, tool_args, campaign)
        collected_results.append({"result": tr.model_dump()})

    # 2. Determine combatants at current location
    loc = campaign.currentLocation
    combatants = [Combatant(**e) for e in LOCATION_ENEMIES.get(loc, [])]

    # 3. Build the single narrative prompt
    prompt = _build_single_shot_prompt(campaign, action, lore_chunks, collected_results, combatants)
    messages = [
        {"role": "system", "content": _get_single_shot_prompt()},
        {"role": "user", "content": prompt},
    ]

    # 4. Single call to Ollama (no tools schema)
    total_input_tokens = 0
    total_output_tokens = 0
    narrative = ""
    try:
        data = _call_ollama(messages)
        total_input_tokens = data.get("prompt_eval_count", 0)
        total_output_tokens = data.get("eval_count", 0)
        narrative = data.get("message", {}).get("content", "")
    except Exception as e:
        logger.warning("single-shot Ollama call failed, using fallback: %s", e)
        narrative = _build_fallback_narrative(campaign, action, collected_results)

    # 5 Determine if combat occurred
    combat_occurred = any(
        tw.get("result", {}).get("toolName") == "apply-damage"
        for tw in collected_results
    )
    enemy_defeated = None
    if combat_occurred:
        import random
        for e in LOCATION_ENEMIES.get(loc, []):
            if random.random() < 0.4:
                enemy_defeated = e["name"]
                break

    # HP / game-over check
    game_over = campaign.playerStats.hp <= 0
    game_over_reason = "death" if game_over else None

    dm_output = DMOutput(
        narrative=narrative,
        characterName=campaign.characterName,
        nextLocation=campaign.currentLocation,
        questUpdate=None,
        combatOccurred=combat_occurred,
        enemyDefeated=enemy_defeated,
        combatants=[],
        gameOver=game_over,
        gameOverReason=game_over_reason,
        dmInternalNote="single-shot mode",
    )

    logger.info("single-shot: %d tools, %d+%d tokens", len(collected_results), total_input_tokens, total_output_tokens)
    return dm_output, collected_results, total_input_tokens, total_output_tokens


# ═══════════════════════════════════════════════════════════════
#  Public dispatcher
# ═══════════════════════════════════════════════════════════════

async def handler(
    campaign: Campaign,
    lore_chunks: list[LoreChunk],
    action: str,
    retry_count: int = 0,
) -> tuple[DMOutput, list[dict], int, int]:
    logger.info("DM_MODE=%s model=%s", config.DM_MODE, config.OLLAMA_MODEL)
    if config.DM_MODE == "agentic":
        return await agentic_handler(campaign, lore_chunks, action, retry_count)
    return await single_shot_handler(campaign, lore_chunks, action, retry_count)
