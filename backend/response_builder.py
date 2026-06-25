from datetime import datetime, timezone
from typing import Any

from models import (
    Campaign, DMOutput, FormattedResponse, DiceRollResult,
    WorkflowStep, LogLine, TurnMetrics, Combatant,
)


def build_response(
    campaign: Campaign,
    dm_output: DMOutput,
    tool_results: list[dict],
    workflow_steps: list[WorkflowStep],
    log_lines: list[LogLine],
    input_tokens: int = 0,
    output_tokens: int = 0,
    retry_count: int = 0,
    started_at: float | None = None,
) -> FormattedResponse:
    dice_rolls: list[DiceRollResult] = []
    leveled_up = False
    new_level = None

    for tw in tool_results:
        tr = tw.get("result", {}) if isinstance(tw, dict) else {}
        if tr.get("toolName") == "roll-dice":
            dice_rolls.append(DiceRollResult(**tr["result"]))
        if tr.get("toolName") == "award-xp":
            xp_result = tr.get("result", {})
            if xp_result.get("leveledUp"):
                leveled_up = True
                new_level = xp_result.get("newLevel")

    active_effect_names = [f"{e.effect} ({e.turnsRemaining}t)" for e in campaign.activeEffects]

    tool_call_names: list[str] = []
    for tw in tool_results:
        tr = tw.get("result", {}) if isinstance(tw, dict) else {}
        name = tr.get("toolName")
        if name:
            tool_call_names.append(name)

    tool_calls_summary = _summarize_tool_calls(tool_call_names)

    metrics = TurnMetrics(
        inputTokens=input_tokens,
        outputTokens=output_tokens,
        toolCalls=tool_calls_summary,
    )

    combatants = dm_output.combatants or []

    response = FormattedResponse(
        campaignId=campaign.campaignId,
        characterName=campaign.characterName,
        characterClass=campaign.characterClass,
        narrative=dm_output.narrative,
        playerStats=campaign.playerStats,
        inventory=campaign.inventory,
        activeEffects=active_effect_names,
        location=campaign.currentLocation,
        diceRolls=dice_rolls,
        workflowTrace=workflow_steps,
        logLines=log_lines,
        metrics=metrics,
        leveledUp=leveled_up,
        newLevel=new_level,
        questUpdate=dm_output.questUpdate,
        gameOver=dm_output.gameOver,
        gameOverReason=dm_output.gameOverReason,
        turnsPlayed=campaign.turnsPlayed,
        specialAbilityState=campaign.specialAbilityState,
        retryCount=retry_count,
        combatants=combatants,
    )

    if started_at:
        logger_fields = {
            "campaignId": campaign.campaignId,
            "latencyMs": int((datetime.now(timezone.utc).timestamp() * 1000) - started_at),
            "success": True,
        }
        log_lines.append(LogLine(
            timestamp=datetime.now(timezone.utc).isoformat(),
            lambdaName="format-response",
            durationMs=0,
            success=True,
            extras=logger_fields,
        ))

    return response


def _summarize_tool_calls(names: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1
    result = []
    for name, count in counts.items():
        if count > 1:
            result.append(f"{name} x{count}")
        else:
            result.append(name)
    return result
