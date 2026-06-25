import uuid
import logging
from typing import Optional

from models import Campaign, PlayerStats, SpecialAbilityState, ActiveEffect, CLASS_STARTING_STATS, CHARACTER_NAMES
from database import get_campaign as db_get_campaign, save_campaign as db_save_campaign

logger = logging.getLogger("neon_scratch.campaign_manager")


def _pick_name(character_class: str) -> str:
    names = CHARACTER_NAMES.get(character_class, ["Adventure Cat"])
    seed = sum(ord(c) for c in character_class)
    return names[seed % len(names)]


def create_campaign(player_id: str, character_class: str) -> Campaign:
    campaign_id = str(uuid.uuid4())
    character_name = _pick_name(character_class)
    stats_dict = CLASS_STARTING_STATS.get(character_class)
    if stats_dict is None:
        raise ValueError(f"Unknown character class: {character_class}")
    stats = PlayerStats(**stats_dict.model_dump())

    campaign = Campaign(
        campaignId=campaign_id,
        playerId=player_id,
        characterClass=character_class,
        characterName=character_name,
        currentLocation="NeonScratchLounge",
        playerStats=stats,
        specialAbilityState=SpecialAbilityState(),
        inventory=[],
        activeEffects=[],
        conversationHistory=[],
        campaignSummary="",
        turnsPlayed=0,
        monstersDefeated=0,
        creditChipsEarned=0,
        questLog=[],
        gameOver=False,
    )
    db_save_campaign(campaign.model_dump())
    logger.info("created campaign id=%s class=%s name=%s", campaign_id, character_class, character_name)
    return campaign


def load_campaign(campaign_id: str) -> Optional[Campaign]:
    raw = db_get_campaign(campaign_id)
    if raw is None:
        return None
    return Campaign(**raw)


def save_campaign(campaign: Campaign) -> None:
    db_save_campaign(campaign.model_dump())
