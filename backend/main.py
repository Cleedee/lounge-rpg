import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import config
import i18n
from models import (
    Campaign, PlayerAction, WorkflowStep, LogLine, DMOutput, Combatant,
    DiceRollResult, TurnMetrics,
)
from database import init_db, save_turn_result, get_turn_result
from campaign_manager import create_campaign, load_campaign, save_campaign
from lore_retriever import load_lore_files, retrieve_lore
from dungeon_master import handler as dm_handler, DMOutputValidationError
from response_builder import build_response

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("neon_scratch")

app = FastAPI(title="Neon Scratch Lounge", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

lore_data = None


def _welcome_narrative(character_class: str) -> str:
    return {
        "TabbyWarrior": i18n.t("main.welcome.TabbyWarrior",
            "The neon sign of the Neon Scratch Lounge flickers overhead as you step out into "
            "Chrome Alley. The rain-slicked pavement reflects a thousand advertisements for things "
            "you don't need and can't afford. A RoombaCore patrol drone hums in the distance.\n\n"
            "Madame Fluffington's voice echoes from the doorway behind you: 'Remember, kid — claws out, "
            "questions later. The resistance is watching.'\n\n"
            "You crack your knuckles. Somewhere in this city, there's a fight with your name on it. "
            "HP: 120/120 | Location: NeonScratchLounge"
        ),
        "SiameseMage": i18n.t("main.welcome.SiameseMage",
            "The electromagnetic haze of Neo-Pawsburg tingles along your fur as you emerge from the "
            "Neon Scratch Lounge. The city's data-streams whisper secrets in frequencies only you can hear. "
            "Above, a RoombaCore billboard flickers — its signal jammer pulses like a headache.\n\n"
            "Madame Fluffington touches your shoulder: 'The tower is humming tonight. They know we're "
            "planning something. Keep your focus, mage.'\n\n"
            "You narrow your eyes. The arcane frequencies of the city bend to your will — or they will, "
            "once you've had enough practice. HP: 70/70 | Location: NeonScratchLounge"
        ),
        "MaineCoonPaladin": i18n.t("main.welcome.MaineCoonPaladin",
            "You fill the doorway of the Neon Scratch Lounge with your magnificent frame. The bell above "
            "the door barely has room to chime as you pass through. Patrons nod with respect — some with "
            "fear — as your fur catches the neon light like a heraldic banner.\n\n"
            "Madame Fluffington looks up from wiping a glass: 'The big one. Good. We need someone the "
            "drones will think twice about.'\n\n"
            "You straighten your posture. The Holy Hairball Shield tingles beneath your fur, ready. "
            "HP: 100/100 | Location: NeonScratchLounge"
        ),
        "SphinxRogue": i18n.t("main.welcome.SphinxRogue",
            "You were never really in the Neon Scratch Lounge. You were near it — close enough to hear "
            "the intel, far enough to see the exits. Now you glide into Chrome Alley like smoke with "
            "a purpose.\n\n"
            "The shadows accept you immediately. A RoombaCore patrol drone sweeps past, oblivious. Its "
            "sensors read empty space where you stand. You smile, which nobody sees.\n\n"
            "Madame Fluffington's voice comes through your earpiece: 'Rogue, you're up. The city belongs "
            "to those who can move through it unseen.' HP: 80/80 | Location: NeonScratchLounge"
        ),
    }.get(character_class, "Your adventure begins.")


def _fallback_narrative(character_class: str) -> tuple[str, int, int]:
    narratives = {
        "TabbyWarrior": (
            i18n.t("main.fallback.TabbyWarrior",
                "The neon flickers. Chrome Alley is quiet — too quiet. A RoombaCore drone sweeps the "
                "street ahead. You tighten your grip on your HackingClaws and prepare. The resistance "
                "is counting on you. HP: 120/120 | Location: NeonScratchLounge"
            ), 0, 0
        ),
        "SiameseMage": (
            i18n.t("main.fallback.SiameseMage",
                "The electromagnetic haze of the city swirls as you step out. A notification flickers "
                "in your peripheral vision: a RoombaCore patrol is approaching. Time to show them what "
                "arcane talent looks like. HP: 70/70 | Location: NeonScratchLounge"
            ), 0, 0
        ),
        "MaineCoonPaladin": (
            i18n.t("main.fallback.MaineCoonPaladin",
                "You stride into Chrome Alley with the confidence of someone who has never been "
                "successfully vacuumed. The drones will learn fear today. HP: 100/100 | Location: "
                "NeonScratchLounge"
            ), 0, 0
        ),
        "SphinxRogue": (
            i18n.t("main.fallback.SphinxRogue",
                "Shadows wrap around you like an old friend. The patrol drone passes within inches — "
                "and sees nothing. You are already three steps ahead, moving toward the objective. "
                "HP: 80/80 | Location: NeonScratchLounge"
            ), 0, 0
        ),
    }
    return narratives.get(character_class, (
        i18n.t("main.fallback.default", "The city hums with neon and danger. Your story begins.",
               hp=80, maxHp=80, location="NeonScratchLounge"), 0, 0
    ))


def _check_ollama() -> bool:
    import httpx
    try:
        resp = httpx.get(f"{config.OLLAMA_BASE_URL}/api/tags", timeout=2)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        model_name = config.OLLAMA_MODEL
        available = any(
            m.get("name") == model_name or m.get("name", "").startswith(model_name)
            for m in models
        )
        if not available:
            logger.warning("Model '%s' not found in Ollama. Available: %s",
                           model_name, [m.get("name") for m in models])
            return False
        return True
    except Exception as e:
        logger.warning("Ollama check failed: %s", e)
        return False


@app.on_event("startup")
async def startup():
    global lore_data
    i18n.load_locale(config.LOCALE)
    init_db()
    lore_data = load_lore_files(config.LORE_DIR)
    logger.info("database initialized, lore loaded from %s", config.LORE_DIR)
    if _check_ollama():
        logger.info("Ollama is reachable at %s", config.OLLAMA_BASE_URL)
    else:
        logger.warning("Ollama not reachable at %s — game will use fallback narratives", config.OLLAMA_BASE_URL)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/action")
async def post_action(pa: PlayerAction):
    global lore_data

    player_id = pa.playerId
    action = pa.action

    if not player_id:
        raise HTTPException(status_code=400, detail=i18n.t("main.error.playerId_required", "playerId is required"))
    if not action:
        raise HTTPException(status_code=400, detail=i18n.t("main.error.action_required", "action is required"))

    campaign: Campaign
    is_new_game = action.lower() == "new-game"

    if is_new_game:
        if not pa.characterClass:
            raise HTTPException(status_code=400, detail=i18n.t("main.error.class_required", "characterClass is required for new-game action"))
        campaign = create_campaign(player_id, pa.characterClass)
        welcome = _welcome_narrative(pa.characterClass)
        return {
            "campaignId": campaign.campaignId,
            "characterName": campaign.characterName,
            "characterClass": campaign.characterClass,
            "narrative": welcome,
            "playerStats": campaign.playerStats.model_dump(),
            "inventory": campaign.inventory,
            "activeEffects": [],
            "location": campaign.currentLocation,
            "diceRolls": [],
            "workflowTrace": [
                {"name": "create-campaign", "label": "Create Campaign", "service": "Lambda",
                 "status": "done", "durationMs": 0},
                {"name": "format-response", "label": "Welcome Message", "service": "App",
                 "status": "done", "durationMs": 0},
            ],
            "logLines": [],
            "metrics": {"inputTokens": 0, "outputTokens": 0, "toolCalls": []},
            "leveledUp": False,
            "newLevel": None,
            "questUpdate": None,
            "gameOver": False,
            "gameOverReason": None,
            "turnsPlayed": 0,
            "specialAbilityState": campaign.specialAbilityState.model_dump(),
            "retryCount": 0,
            "combatants": [],
        }

    if not pa.campaignId:
        raise HTTPException(status_code=400, detail=i18n.t("main.error.campaignId_required", "campaignId is required for existing campaigns"))

    campaign = load_campaign(pa.campaignId)
    if campaign is None:
        raise HTTPException(status_code=404, detail=i18n.t("main.error.campaign_not_found", "Campaign {campaignId} not found", campaignId=pa.campaignId))
    if campaign.gameOver:
        raise HTTPException(status_code=400, detail=i18n.t("main.error.campaign_ended", "This campaign has ended. Start a new game."))

    correlation_id = str(uuid.uuid4())
    started_at_ms = time.time() * 1000
    timestamp_iso = datetime.now(timezone.utc).isoformat()

    save_turn_result(correlation_id, campaign.campaignId, "running")

    workflow_steps: list[WorkflowStep] = []
    log_lines: list[LogLine] = []
    retry_count = 0

    # Step 1: Retrieve Lore
    step_start = time.time()
    try:
        chunks = retrieve_lore(action, lore_data, campaign.currentLocation)
    except Exception as e:
        logger.error("lore retrieval failed: %s", e)
        chunks = []
    workflow_steps.append(WorkflowStep(
        name="retrieve-lore", label="Retrieve Lore", service="Lambda",
        status="done", durationMs=int((time.time() - step_start) * 1000),
    ))
    log_lines.append(LogLine(
        timestamp=timestamp_iso, lambdaName="retrieve-lore",
        durationMs=int((time.time() - step_start) * 1000),
        success=True, extras={"chunks": len(chunks)},
    ))

    # Step 2: Invoke Dungeon Master
    oliama_available = _check_ollama()
    step_start = time.time()
    dm_output: DMOutput | None = None
    tool_results: list[dict] = []
    input_tokens = 0
    output_tokens = 0

    if oliama_available:
        try:
            dm_output, tool_results, input_tokens, output_tokens = await dm_handler(
                campaign, chunks, action, retry_count
            )
            workflow_steps.append(WorkflowStep(
                name="invoke-dungeon-master", label="Invoke Dungeon Master", service="Ollama",
                status="done", durationMs=int((time.time() - step_start) * 1000),
            ))
            log_lines.append(LogLine(
                timestamp=datetime.now(timezone.utc).isoformat(), lambdaName="invoke-dungeon-master",
                durationMs=int((time.time() - step_start) * 1000),
                success=True, extras={"toolCalls": len(tool_results)},
            ))
        except DMOutputValidationError as e:
            logger.error("DM validation error: %s", e)
            workflow_steps.append(WorkflowStep(
                name="invoke-dungeon-master", label="Invoke Dungeon Master", service="Ollama",
                status="failed", durationMs=int((time.time() - step_start) * 1000),
            ))
            raise HTTPException(status_code=500, detail=i18n.t("main.error.dm_validation", "DM validation error: {error}", error=str(e)))
        except Exception as e:
            logger.error("DM handler error: %s", e)
            workflow_steps.append(WorkflowStep(
                name="invoke-dungeon-master", label="Invoke Dungeon Master", service="Ollama",
                status="failed", durationMs=int((time.time() - step_start) * 1000),
            ))
            raise HTTPException(status_code=500, detail=i18n.t("main.error.dm_handler", "Dungeon Master error: {error}", error=str(e)))
    else:
        narrative, _, _ = _fallback_narrative(campaign.characterClass)
        dm_output = DMOutput(
            narrative=narrative,
            characterName=campaign.characterName,
            dmInternalNote=i18n.t("main.ollama_not_available", "Ollama not available — fallback narrative"),
        )
        workflow_steps.append(WorkflowStep(
            name="invoke-dungeon-master", label="Invoke Dungeon Master", service="Ollama",
            status="done", durationMs=0,
        ))
        log_lines.append(LogLine(
            timestamp=datetime.now(timezone.utc).isoformat(), lambdaName="invoke-dungeon-master",
            durationMs=0, success=True, extras={"fallback": True},
        ))

    # Step 3: Persist Campaign
    step_start = time.time()
    campaign.turnsPlayed += 1
    campaign.conversationHistory.append({"role": "user", "content": action})
    campaign.conversationHistory.append({"role": "assistant", "content": dm_output.narrative})
    if len(campaign.conversationHistory) > config.MAX_CONVERSATION_HISTORY * 2:
        trim = config.HISTORY_TRIM_COUNT
        campaign.conversationHistory = (
            campaign.conversationHistory[:trim]
            + campaign.conversationHistory[-(config.MAX_CONVERSATION_HISTORY - trim):]
        )
    if dm_output.gameOver:
        campaign.gameOver = True
    if dm_output.enemyDefeated:
        campaign.monstersDefeated += 1
    save_campaign(campaign)
    workflow_steps.append(WorkflowStep(
        name="persist-campaign", label="Persist Campaign", service="Lambda",
        status="done", durationMs=int((time.time() - step_start) * 1000),
    ))

    # Step 4: Build response
    step_start = time.time()
    dice_rolls = []
    leveled_up = False
    new_level = None
    for tw in tool_results:
        tr = tw.get("result", {}) if isinstance(tw, dict) else {}
        if tr.get("toolName") == "roll-dice":
            dice_rolls.append(DiceRollResult(**tr["result"]))
        if tr.get("toolName") == "award-xp":
            xr = tr.get("result", {})
            if xr.get("leveledUp"):
                leveled_up = True
                new_level = xr.get("newLevel")

    active_effect_names = [f"{e.effect} ({e.turnsRemaining}t)" for e in campaign.activeEffects]

    tool_call_names = []
    for tw in tool_results:
        tr = tw.get("result", {}) if isinstance(tw, dict) else {}
        name = tr.get("toolName")
        if name:
            tool_call_names.append(name)

    counts = {}
    for n in tool_call_names:
        counts[n] = counts.get(n, 0) + 1
    tcs = [f"{n} x{c}" if c > 1 else n for n, c in counts.items()]

    response = {
        "campaignId": campaign.campaignId,
        "characterName": campaign.characterName,
        "characterClass": campaign.characterClass,
        "narrative": dm_output.narrative,
        "playerStats": campaign.playerStats.model_dump(),
        "inventory": campaign.inventory,
        "activeEffects": active_effect_names,
        "location": campaign.currentLocation,
        "diceRolls": [r.model_dump() for r in dice_rolls],
        "workflowTrace": [s.model_dump() for s in workflow_steps],
        "logLines": [l.model_dump() for l in log_lines],
        "metrics": {"inputTokens": input_tokens, "outputTokens": output_tokens, "toolCalls": tcs},
        "leveledUp": leveled_up,
        "newLevel": new_level,
        "questUpdate": dm_output.questUpdate,
        "gameOver": dm_output.gameOver,
        "gameOverReason": dm_output.gameOverReason,
        "turnsPlayed": campaign.turnsPlayed,
        "specialAbilityState": campaign.specialAbilityState.model_dump(),
        "retryCount": retry_count,
        "combatants": [c.model_dump() for c in (dm_output.combatants or [])],
    }

    response["workflowTrace"].append({
        "name": "format-response", "label": "Format Response", "service": "Lambda",
        "status": "done", "durationMs": int((time.time() - step_start) * 1000),
    })

    save_turn_result(correlation_id, campaign.campaignId, "complete", response)

    return response


@app.get("/action/status")
async def get_action_status(turnId: str):
    result = get_turn_result(turnId)
    if result is None:
        return {"status": "not_found"}
    return result


@app.post("/demo/inject-failure")
async def inject_failure():
    config.FORCE_TOOL_FAILURE = True
    logger.warning("failure injection ENABLED")
    return {"status": "failure_injected"}


@app.post("/demo/clear-failure")
async def clear_failure():
    config.FORCE_TOOL_FAILURE = False
    logger.warning("failure injection CLEARED")
    return {"status": "failure_cleared"}


@app.get("/demo/logs")
async def fetch_logs(campaignId: str):
    from database import get_connection
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM turn_results WHERE campaign_id = ? ORDER BY created_at DESC LIMIT 20",
            (campaignId,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
