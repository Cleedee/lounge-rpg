import json
import os
from backend.heranca.models import Arma, Armadura, SetorInfo, EventoInfo

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def carregar_setores() -> dict[str, SetorInfo]:
    raw = _load_json(os.path.join(DATA_DIR, "sectors.json"))
    setores = {}
    for s in raw["sectors"]:
        setores[s["id"]] = SetorInfo(
            id=s["id"],
            nome=s["name"],
            descricao=s["description"],
            conexoes=s.get("connections", []),
            perigo=s.get("danger_level", 2),
            features=s.get("features", []),
        )
    return setores


def carregar_eventos(setor_id: str) -> list[EventoInfo]:
    path = os.path.join(DATA_DIR, "events", f"{setor_id}.json")
    if not os.path.exists(path):
        return []
    raw = _load_json(path)
    eventos = []
    for e in raw["events"]:
        eventos.append(EventoInfo(
            rolagem=e["roll"],
            titulo=e.get("title", ""),
            descricao=e.get("description", e.get("descricao", "")),
            tipo=e.get("type", "neutral"),
            requer_teste=e.get("requires_test", False),
            atributo=e.get("attribute"),
            pericia=e.get("skill"),
            sucesso=e.get("success"),
            falha=e.get("failure"),
            recompensas=e.get("rewards"),
            leva_encontro=e.get("leads_to_encounter", False),
            tipo_encontro=e.get("encounter_type"),
            especial=e.get("special"),
        ))
    return eventos


def carregar_armas() -> list[Arma]:
    raw = _load_json(os.path.join(DATA_DIR, "items.json"))
    armas = []
    for w in raw["weapons"]:
        dano = w["damage"]
        bonus = 0
        fixo = None
        if dano.startswith("Corpo"):
            bonus = int(dano.split("+")[1]) if "+" in dano else 0
        elif "fixo" in dano:
            fixo = int(dano.split()[0])
        try:
            maos_val = int(w.get("hands", 1))
        except (ValueError, TypeError):
            maos_val = 0
        armas.append(Arma(
            nome=w["name"],
            dano_bonus=bonus,
            tipo=w.get("type", "melee"),
            maos=maos_val,
            dano_fixo=fixo,
        ))
    return armas


def carregar_armaduras() -> list[Armadura]:
    raw = _load_json(os.path.join(DATA_DIR, "items.json"))
    armaduras = []
    for a in raw["armor"]:
        armaduras.append(Armadura(
            nome=a["name"],
            reducao=a["reduction"],
            penalidade=a.get("penalty"),
        ))
    return armaduras


def carregar_adversarios() -> list[dict]:
    raw = _load_json(os.path.join(DATA_DIR, "adversaries.json"))
    return raw["adversaries"]


def carregar_refugios_base() -> list[dict]:
    raw = _load_json(os.path.join(DATA_DIR, "refuges.json"))
    return raw["refuges"]


def carregar_upgrades() -> list[dict]:
    raw = _load_json(os.path.join(DATA_DIR, "refuges.json"))
    return raw.get("refuge_upgrades", [])


def carregar_recursos() -> dict:
    raw = _load_json(os.path.join(DATA_DIR, "items.json"))
    return raw.get("resources", {})
