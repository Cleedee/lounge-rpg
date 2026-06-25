from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


class SpecialAbilityState(BaseModel):
    nineLivesUsed: bool = False
    vanishCooldownTurnsLeft: int = 0
    shieldUsedThisEncounter: bool = False


class PlayerStats(BaseModel):
    hp: int
    maxHp: int
    pawStrength: int
    agility: int
    arcane: int
    stealth: int
    gold: int
    level: int
    xp: int


class ActiveEffect(BaseModel):
    effect: str
    turnsRemaining: int


class Campaign(BaseModel):
    campaignId: str
    playerId: str
    characterClass: str
    characterName: str
    currentLocation: str
    playerStats: PlayerStats
    specialAbilityState: SpecialAbilityState
    inventory: list[str]
    activeEffects: list[ActiveEffect]
    conversationHistory: list[dict]
    campaignSummary: str
    turnsPlayed: int
    monstersDefeated: int
    creditChipsEarned: int
    questLog: list[str]
    gameOver: bool


class PlayerAction(BaseModel):
    playerId: str
    action: str
    campaignId: Optional[str] = None
    characterClass: Optional[str] = None


class LoreChunk(BaseModel):
    content: str
    score: float
    location: Optional[str] = None


class Combatant(BaseModel):
    name: str
    hp: int
    maxHp: int


class DMOutput(BaseModel):
    narrative: str
    characterName: str
    toolCalls: list = []
    nextLocation: Optional[str] = None
    questUpdate: Optional[str] = None
    combatOccurred: bool = False
    enemyDefeated: Optional[str] = None
    combatants: list[Combatant] = []
    gameOver: bool = False
    gameOverReason: Optional[str] = None
    dmInternalNote: str = ""


class DiceRollResult(BaseModel):
    rolls: list[int]
    modifier: int
    statBonus: int
    total: int
    purpose: str


class DamageResult(BaseModel):
    previousHp: int
    newHp: int
    damageBlocked: int
    nineLivesTrigger: bool
    isDead: bool


class InventoryResult(BaseModel):
    inventory: list[str]
    gold: int
    effectApplied: Optional[str] = None


class XpResult(BaseModel):
    previousLevel: int
    newLevel: int
    newXp: int
    leveledUp: bool
    statImproved: Optional[str] = None


class LocationResult(BaseModel):
    previousLocation: str
    newLocation: str
    locationDescription: str


class EffectResult(BaseModel):
    activeEffects: list[ActiveEffect]


class SpecialAbilityResult(BaseModel):
    abilityUsed: str
    mechanicalEffect: str
    cooldownSet: Optional[int] = None


class QuestLogResult(BaseModel):
    questLog: list[str]


class ToolResult(BaseModel):
    toolName: str
    result: dict


class WorkflowStep(BaseModel):
    name: str
    label: str
    service: str
    status: str
    durationMs: Optional[int] = None
    retryAttempt: Optional[int] = None
    maxRetries: Optional[int] = None


class LogLine(BaseModel):
    timestamp: str
    lambdaName: str
    durationMs: int
    success: bool
    errorType: Optional[str] = None
    extras: Optional[dict] = None


class TurnMetrics(BaseModel):
    inputTokens: int = 0
    outputTokens: int = 0
    toolCalls: list[str] = []


class FormattedResponse(BaseModel):
    campaignId: str
    characterName: str
    characterClass: str
    narrative: str
    playerStats: PlayerStats
    inventory: list[str]
    activeEffects: list[str]
    location: str
    diceRolls: list[DiceRollResult] = []
    workflowTrace: list[WorkflowStep] = []
    logLines: list[LogLine] = []
    metrics: TurnMetrics = TurnMetrics()
    leveledUp: bool = False
    newLevel: Optional[int] = None
    questUpdate: Optional[str] = None
    gameOver: bool = False
    gameOverReason: Optional[str] = None
    turnsPlayed: int = 0
    specialAbilityState: SpecialAbilityState = SpecialAbilityState()
    retryCount: int = 0
    combatants: list[Combatant] = []


CLASS_STARTING_STATS: dict[str, PlayerStats] = {
    "TabbyWarrior": PlayerStats(hp=120, maxHp=120, pawStrength=8, agility=5, arcane=2, stealth=4, gold=10, level=1, xp=0),
    "SiameseMage": PlayerStats(hp=70, maxHp=70, pawStrength=3, agility=6, arcane=9, stealth=5, gold=15, level=1, xp=0),
    "MaineCoonPaladin": PlayerStats(hp=100, maxHp=100, pawStrength=6, agility=3, arcane=5, stealth=2, gold=20, level=1, xp=0),
    "SphinxRogue": PlayerStats(hp=80, maxHp=80, pawStrength=4, agility=9, arcane=4, stealth=9, gold=25, level=1, xp=0),
}

CHARACTER_NAMES: dict[str, list[str]] = {
    "TabbyWarrior": ["Garras McGee", "Sargento Fofucho", "Rex Patada", "Bruto Listrado"],
    "SiameseMage": ["Sussurro de Seda", "Madame Pata Azul", "O Pontista Azul", "Oráculo Miau"],
    "MaineCoonPaladin": ["Sir Fofinho III", "Irmão Patona", "A Juba Justa", "Paladino Queijo"],
    "SphinxRogue": ["Pata de Areia", "O Sem Nome", "Fantasma do Beco", "Nulo"],
}

KNOWN_LOCATIONS: list[str] = [
    "NeonScratchLounge",
    "ChromeAlley",
    "RoombaCoreTower",
    "NightMarket",
    "SewersOfForgetfulness",
    "IndustrialZone",
]

ALLOWED_TOOLS: list[str] = [
    "roll-dice",
    "apply-damage",
    "update-inventory",
    "award-xp",
    "update-location",
    "apply-effect",
    "use-special-ability",
    "update-quest-log",
]
