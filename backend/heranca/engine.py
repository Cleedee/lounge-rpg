import random
import json
from backend.heranca.models import (
    EstadoJogo, Sobrevivente, Refugio, UpgradeRefugio, Stats,
    Arma, Armadura, HordaInfo, HexCoordenada, SetorHex,
    FaseDia, Atributo, PERICIAS,
)
from backend.heranca.data_loader import (
    carregar_setores, carregar_eventos, carregar_armas,
    carregar_armaduras, carregar_adversarios, carregar_refugios_base,
    carregar_upgrades, carregar_recursos,
)

TODAS_ARMAS = carregar_armas()
TODAS_ARMADURAS = carregar_armaduras()
TODOS_ADVERSARIOS = carregar_adversarios()
SETORES = carregar_setores()
REFUGIOS_BASE = carregar_refugios_base()
UPGRADES = carregar_upgrades()
RECURSOS = carregar_recursos()

# Hex grid: axial coordinate offsets for 6 neighbors (pointy-top)
HEX_OFFSETS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]


DIRECOES = {
    (1, 0): "L", (-1, 0): "O",
    (0, 1): "SE", (0, -1): "NO",
    (1, -1): "NE", (-1, 1): "SO",
}

DIRECOES_NOME = {
    (1, 0): "Leste", (-1, 0): "Oeste",
    (0, 1): "Sudeste", (0, -1): "Noroeste",
    (1, -1): "Nordeste", (-1, 1): "Sudoeste",
}


def hex_chave(q: int, r: int) -> str:
    return f"{q},{r}"


def hex_vizinhos(q: int, r: int) -> list[tuple[int, int]]:
    return [(q + dq, r + dr) for dq, dr in HEX_OFFSETS]


def direcao_entre(q_origem: int, r_origem: int, q_destino: int, r_destino: int) -> tuple[str, str]:
    dq, dr = q_destino - q_origem, r_destino - r_origem
    sigla = DIRECOES.get((dq, dr), "?")
    nome = DIRECOES_NOME.get((dq, dr), "Desconhecida")
    return sigla, nome


def hex_tipo(estado: EstadoJogo) -> str | None:
    setor_hex = estado.mapa.get(hex_chave(estado.setor_atual.q, estado.setor_atual.r))
    return setor_hex.tipo if setor_hex else None


def hex_info(estado: EstadoJogo):
    tipo_id = hex_tipo(estado)
    if not tipo_id:
        return None
    return SETORES.get(tipo_id)


def _sortear_caracteristica(tipo: str, usadas: set[str]) -> str:
    info = SETORES.get(tipo)
    if not info or not info.features:
        return ""
    disp = [f for f in info.features if f not in usadas]
    if not disp:
        disp = info.features
    escolha = random.choice(disp)
    usadas.add(escolha)
    return escolha


def gerar_mapa_padrao() -> dict[str, SetorHex]:
    tipos = list(SETORES.keys())
    usadas: set[str] = set()
    mapa: dict[str, SetorHex] = {}
    mapa["0,0"] = SetorHex(
        tipo=tipos[0], coordenadas=HexCoordenada(q=0, r=0),
        caracteristica=_sortear_caracteristica(tipos[0], usadas),
    )
    for i, (dq, dr) in enumerate(HEX_OFFSETS[:5]):
        q, r = dq, dr
        tipo = tipos[(i + 1) % len(tipos)]
        mapa[hex_chave(q, r)] = SetorHex(
            tipo=tipo, coordenadas=HexCoordenada(q=q, r=r),
            caracteristica=_sortear_caracteristica(tipo, usadas),
        )
    return mapa


def d10() -> int:
    return random.randint(1, 10)


def d10_rolar() -> int:
    return random.randint(0, 9)


def rolar_teste(atributo_valor: int, pericia_bonus: int = 0, vantagem: bool = False, desvantagem: bool = False) -> dict:
    if vantagem and desvantagem:
        vantagem = False
        desvantagem = False
    if vantagem:
        r1, r2 = d10(), d10()
        resultado = max(r1, r2)
        rolagens = [r1, r2]
    elif desvantagem:
        r1, r2 = d10(), d10()
        resultado = min(r1, r2)
        rolagens = [r1, r2]
    else:
        resultado = d10()
        rolagens = [resultado]
    total = resultado + atributo_valor + pericia_bonus
    sucesso = total >= 10
    bonus_poder = max(0, total - 10)
    return {
        "rolagens": rolagens,
        "atributo": atributo_valor,
        "pericia": pericia_bonus,
        "total": total,
        "sucesso": sucesso,
        "bonus_poder": bonus_poder,
    }


def calcular_atributo(estado: EstadoJogo, atributo: str) -> int:
    s = estado.sobrevivente.stats
    return {
        "Corpo": s.corpo,
        "Mente": s.mente,
        "Espírito": s.espirito,
        "Espirito": s.espirito,
    }.get(atributo, 1)


def calcular_pericia(estado: EstadoJogo, pericia: str) -> int:
    if pericia in estado.sobrevivente.pericias:
        return 2
    return 0


def tem_vantagem(estado: EstadoJogo, pericia: str, local: str = "") -> bool:
    return False


def tem_desvantagem(estado: EstadoJogo, pericia: str, local: str = "") -> bool:
    s = estado.sobrevivente
    if s.fome_marcadores >= s.stats.corpo:
        return True
    if s.loucura_marcadores >= s.stats.mente:
        return True
    armadura = s.armadura_equipada
    if armadura and armadura.penalidade and "destreza" in armadura.penalidade.lower():
        if pericia in ("Atletismo", "Subterfúgio"):
            return True
    return False


def testar(estado: EstadoJogo, atributo: str, pericia: str = "") -> dict:
    atr_val = calcular_atributo(estado, atributo)
    per_val = calcular_pericia(estado, pericia)
    vant = tem_vantagem(estado, pericia)
    desv = tem_desvantagem(estado, pericia)
    return rolar_teste(atr_val, per_val, vant, desv)


def sofrer_dano(estado: EstadoJogo, dano: int, tipo_dano: str = "fisico") -> int:
    s = estado.sobrevivente
    reducao = 0
    if tipo_dano == "fisico" and s.armadura_equipada:
        reducao = s.armadura_equipada.reducao
    dano_real = max(0, dano - reducao)
    s.saude = max(0, s.saude - dano_real)
    return dano_real


def sofrer_dano_vontade(estado: EstadoJogo, dano: int) -> int:
    s = estado.sobrevivente
    s.vontade = max(0, s.vontade - dano)
    return dano


def adicionar_loucura(estado: EstadoJogo, quantidade: int = 1):
    s = estado.sobrevivente
    s.loucura_marcadores += quantidade


def adicionar_fome(estado: EstadoJogo, quantidade: int = 1):
    s = estado.sobrevivente
    s.fome_marcadores += quantidade


def consumir_comida(estado: EstadoJogo, quantidade: int = 1):
    s = estado.sobrevivente
    s.fome_marcadores = max(0, s.fome_marcadores - quantidade)


def avancar_hora(estado: EstadoJogo, horas: float):
    estado.hora += horas
    while estado.hora >= 24:
        estado.hora -= 24
        estado.dia += 1
    _atualizar_fase(estado)


def _atualizar_fase(estado: EstadoJogo):
    h = estado.hora
    if 6 <= h < 12:
        estado.fase = FaseDia.MANHA
    elif 12 <= h < 18:
        estado.fase = FaseDia.TARDE
    else:
        estado.fase = FaseDia.NOITE


def iniciar_estado() -> EstadoJogo:
    estado = EstadoJogo()
    estado.mapa = gerar_mapa_padrao()
    estado.refugio.setor_id = hex_chave(estado.setor_atual.q, estado.setor_atual.r)
    _atualizar_fase(estado)
    return estado


def setores_disponiveis(estado: EstadoJogo) -> list[tuple[int, int, str, str, str]]:
    vizinhos = []
    atuais = hex_vizinhos(estado.setor_atual.q, estado.setor_atual.r)
    for q, r in atuais:
        chave = hex_chave(q, r)
        setor_hex = estado.mapa.get(chave)
        if setor_hex:
            tipo_info = SETORES.get(setor_hex.tipo)
            nome = tipo_info.nome if tipo_info else setor_hex.tipo
            sigla, nome_dir = direcao_entre(estado.setor_atual.q, estado.setor_atual.r, q, r)
            vizinhos.append((q, r, nome, sigla, setor_hex.caracteristica))
    return vizinhos


def mover_setor(estado: EstadoJogo, q: int, r: int, veiculo: bool = False) -> str:
    chave_dest = hex_chave(q, r)
    if chave_dest not in estado.mapa:
        return "Este hexágono não existe no mapa."
    if (q, r) not in hex_vizinhos(estado.setor_atual.q, estado.setor_atual.r):
        return "Setor muito distante. Você só pode ir para setores adjacentes."
    horas = 0.5 if veiculo else 1
    sigla, nome_dir = direcao_entre(estado.setor_atual.q, estado.setor_atual.r, q, r)
    estado.setor_atual = HexCoordenada(q=q, r=r)
    avancar_hora(estado, horas)
    if chave_dest not in estado.locais_visitados:
        estado.locais_visitados.append(chave_dest)
    setor_hex = estado.mapa[chave_dest]
    tipo_info = SETORES.get(setor_hex.tipo)
    nome = tipo_info.nome if tipo_info else setor_hex.tipo
    mins = int(horas * 60)
    return f"Você se deslocou para [{sigla}] {nome}. ({mins}min gastos)"


def rolar_evento(estado: EstadoJogo) -> EventoInfo | None:
    tipo_id = hex_tipo(estado)
    if not tipo_id:
        return None
    eventos = carregar_eventos(tipo_id)
    if not eventos:
        return None
    d1 = d10()
    if d1 <= 5:
        metade = 0
    else:
        metade = 1
    d2 = d10_rolar()
    num_evento = (metade * 10) + (d2 if d2 != 0 else 10)
    for e in eventos:
        if e.rolagem == num_evento:
            return e
    if eventos:
        return eventos[num_evento % len(eventos)]
    return None


def resolver_evento(estado: EstadoJogo, evento: EventoInfo) -> dict:
    resultado = {
        "titulo": evento.titulo,
        "descricao": evento.descricao,
        "tipo": evento.tipo,
        "sucesso": None,
        "rolagem_teste": None,
        "recompensas": None,
        "leva_encontro": evento.leva_encontro,
    }

    if evento.requer_teste and evento.atributo:
        r = testar(estado, evento.atributo, evento.pericia or "")
        resultado["rolagem_teste"] = r
        if r["sucesso"]:
            resultado["sucesso"] = True
            resultado["narrativa"] = evento.sucesso or "Sucesso!"
            if evento.recompensas:
                resultado["recompensas"] = evento.recompensas
                _aplicar_recompensas(estado, evento.recompensas)
        else:
            resultado["sucesso"] = False
            resultado["narrativa"] = evento.falha or "Falha!"
            if evento.recompensas and "penalidade" in evento.recompensas:
                _aplicar_recompensas(estado, evento.recompensas)

    if evento.tipo == "supernatural" and not resultado.get("sucesso", True):
        adicionar_loucura(estado, 1)
        resultado["loucura"] = 1

    return resultado


def _aplicar_recompensas(estado: EstadoJogo, recompensas: dict):
    from backend.heranca.models import Item
    s = estado.sobrevivente
    if "food" in recompensas:
        qtd = recompensas["food"]
        for _ in range(qtd):
            s.inventario.append(Item(nome="Comida", quantidade=1))
    if "items" in recompensas:
        for item in recompensas["items"]:
            if isinstance(item, dict):
                s.inventario.append(Item(nome=item["name"], quantidade=item.get("qty", 1)))
            else:
                s.inventario.append(Item(nome=str(item), quantidade=1))


def verificar_encontro_violento(estado: EstadoJogo) -> bool:
    r = d10()
    return r <= 2


def gerar_encontro_violento(estado: EstadoJogo) -> dict | None:
    if not TODOS_ADVERSARIOS:
        return None
    r1, r2 = d10_rolar(), d10_rolar()
    adv = random.choice(TODOS_ADVERSARIOS)
    qtd = 1
    if adv.get("perigo", 1) <= 1:
        qtd = random.randint(2, 5)
    elif adv.get("perigo", 1) <= 2:
        qtd = random.randint(1, 3)
    return {
        "adversario": adv,
        "quantidade": qtd,
        "descricao": f"{qtd}x {adv['name']}: {adv['description']}",
    }


def rolar_ataque_horda(estado: EstadoJogo) -> HordaInfo | None:
    r = d10()
    if r > 2:
        return None
    r2 = d10_rolar()
    if r2 <= 1:
        qtd = 50 + d10() + d10() + d10() + d10() + d10()
        return HordaInfo(tipo="Desmortos", quantidade=qtd,
                         descricao=f"{qtd} Desmortos seguem como um vagalhão na direção de seu Refúgio.")
    elif r2 <= 3:
        qtd = 30 + d10() + d10()
        return HordaInfo(tipo="Carniçais", quantidade=qtd,
                         descricao=f"{qtd} Carniçais sentem o cheiro dos Sobreviventes e cercam seu Refúgio.")
    elif r2 <= 5:
        qtd = 30 + d10() + d10()
        return HordaInfo(tipo="Insanos", quantidade=qtd,
                         descricao=f"{qtd} Insanos armados descobrem a localização de seu Refúgio e atacam.")
    elif r2 <= 7:
        qtd = 20 + d10()
        return HordaInfo(tipo="Abissais", quantidade=qtd,
                         descricao=f"{qtd} Abissais são ordenados por um Sacerdote Sombrio a atacarem seu Refúgio.")
    else:
        antigos = ["Nyarlathotep", "Yig", "Hastur", "Cthulhu"]
        r3 = d10_rolar()
        idx = 0 if r3 <= 3 else 1 if r3 <= 5 else 2 if r3 <= 7 else 3
        nome = antigos[idx]
        return HordaInfo(tipo="Grande Antigo", quantidade=1,
                         descricao=f"{nome} se aproxima de seu Refúgio!")


def passar_noite(estado: EstadoJogo, no_refugio: bool = True) -> dict:
    resultado = {
        "horda": None,
        "descanso": True,
        "msg": "",
    }

    horda = rolar_ataque_horda(estado)
    if horda:
        resultado["horda"] = horda
        if no_refugio:
            resultado["msg"] = f"Um ataque de Horda ocorreu! {horda.descricao} Seu Refúgio sofreu o ataque."
        else:
            resultado["msg"] = f"Um ataque de Horda ocorreu! {horda.descricao} Você está fora do Refúgio — luta sem proteção!"

    estado.hora = 6
    estado.dia += 1
    estado.fase = FaseDia.MANHA
    estado.encontros_hoje = 0
    estado.horda_atacou_hoje = False
    estado.descansou_hoje = False

    s = estado.sobrevivente
    if no_refugio:
        cura = 1
        if any(u.nome == "Oficina" and u.ativo for u in estado.refugio.upgrades):
            cura = 2
        if any(u.nome == "Horta" and u.ativo for u in estado.refugio.upgrades):
            cura += 1
        s.saude = min(s.stats.saude_max, s.saude + cura)
    s.vontade = min(s.stats.vontade_max, s.vontade + 1)

    consumir_comida(estado, 1)

    return resultado


def processar_fome_diaria(estado: EstadoJogo) -> str:
    from backend.heranca.models import Item
    s = estado.sobrevivente
    tem_horta = any(u.nome == "Horta" and u.ativo for u in estado.refugio.upgrades)
    tem_cisterna = any(u.nome == "Cisterna" and u.ativo for u in estado.refugio.upgrades)

    if tem_horta and not any(item.nome == "Comida" for item in s.inventario):
        s.inventario.append(Item(nome="Comida", quantidade=1))

    tem_comida = any(item.nome == "Comida" for item in s.inventario)
    if tem_comida:
        for i, item in enumerate(s.inventario):
            if item.nome == "Comida":
                item.quantidade -= 1
                if item.quantidade <= 0:
                    s.inventario.pop(i)
                break
        consumir_comida(estado, 1)
        return "Você consumiu 1 comida."
    adicionar_fome(estado, 1)
    if s.fome_marcadores >= s.stats.saude_max:
        estado.encerrado = True
        estado.causa_morte = "Fome"
        return "Você morreu de fome."
    if s.fome_marcadores >= s.stats.corpo:
        return "Fome crítica! Desvantagem em todos os testes."
    return f"Fome: {s.fome_marcadores}/{s.stats.corpo} (crítico), {s.stats.saude_max} (máximo)."


def atacar_adversario(estado: EstadoJogo, adv: dict, distancia: str = "corporal") -> dict:
    s = estado.sobrevivente
    arma = s.arma_equipada or Arma(nome="Desarmado", dano_bonus=0, tipo="melee", maos=0)

    if distancia == "distancia" and arma.tipo not in ("ranged", "explosive"):
        return {"erro": "Arma corpo a corpo não funciona à distância."}

    pericia = "Combate Corporal" if distancia == "corporal" else "Combate a Distância"
    per_val = calcular_pericia(estado, pericia)

    r = rolar_teste(s.stats.corpo, per_val, tem_vantagem(estado, pericia), tem_desvantagem(estado, pericia))

    dano = 0
    if r["sucesso"]:
        if arma.dano_fixo:
            dano = arma.dano_fixo + r["bonus_poder"]
        else:
            dano = s.stats.corpo + arma.dano_bonus + r["bonus_poder"]

    return {
        "rolagem": r,
        "dano": dano,
        "arma": arma.nome,
    }


def reagir_adversario(adv: dict, dano_recebido: int) -> dict:
    saude = adv.get("stats", {}).get("saude", 0)
    if isinstance(saude, str):
        return {"dano": 0, "descricao": f"{adv['name']} é imune a ataques físicos."}

    if "reaction" in adv:
        return {"dano": 4, "descricao": adv["reaction"]}

    dano_base = 4
    if adv.get("perigo", 1) >= 3:
        dano_base = 6
    if adv.get("perigo", 1) >= 4:
        dano_base = 8

    return {"dano": dano_base, "descricao": f"{adv['name']} revida causando {dano_base} de dano."}


def ataque_ao_refugio(estado: EstadoJogo, horda: HordaInfo) -> dict:
    r = estado.refugio
    dano_horda = horda.quantidade // 10 + 5
    tem_muralha = any(u.nome == "Muralha" and u.ativo for u in r.upgrades)
    tem_torre = any(u.nome == "Torre de Vigia" and u.ativo for u in r.upgrades)
    tem_radio = any(u.nome == "Rádio" and u.ativo for u in r.upgrades)

    if tem_muralha:
        dano_horda = max(0, dano_horda - 10)
    if tem_torre:
        dano_horda = max(0, dano_horda - 6)
    if tem_radio and horda.tipo == "Insanos":
        dano_horda = max(0, dano_horda - 4)

    r.defesa = max(0, r.defesa - dano_horda)

    resultado = f"Horda causou {dano_horda} de dano ao Refúgio. Defesa restante: {r.defesa}/{r.defesa_max}."

    if r.defesa <= 0:
        resultado += " O Refúgio foi invadido! Os inimigos estão dentro."
        s = estado.sobrevivente
        dano_invasao = horda.quantidade // 20
        sofrer_dano(estado, dano_invasao)
        resultado += f" Você sofreu {dano_invasao} de dano no combate interno."

    return {"resultado": resultado, "dano_horda": dano_horda, "defesa_restante": r.defesa}


def construir_upgrade(estado: EstadoJogo, nome_upgrade: str) -> str:
    r = estado.refugio
    upgrade_info = next((u for u in UPGRADES if u["name"].lower() == nome_upgrade.lower()), None)
    if not upgrade_info:
        return f"Upgrade '{nome_upgrade}' não encontrado."

    if any(u.nome == upgrade_info["name"] and u.ativo for u in r.upgrades):
        return f"Upgrade '{upgrade_info['name']}' já instalado."

    espaco_custo = 1
    if upgrade_info["name"] == "Horta":
        espaco_custo = 2

    if r.espaco < espaco_custo:
        return f"Espaço insuficiente. Precisa de {espaco_custo}, tem {r.espaco}."

    r.upgrades.append(UpgradeRefugio(nome=upgrade_info["name"], ativo=True))
    r.espaco -= espaco_custo

    if upgrade_info["name"] == "Muralha":
        r.defesa_max += 10
        r.defesa += 10
    elif upgrade_info["name"] == "Gerador":
        r.tecnologia = min(r.tecnologia_max, r.tecnologia + 2)
    elif upgrade_info["name"] == "Cisterna":
        from backend.heranca.models import Item
        tem_agua = any(i.nome == "Água" for i in estado.sobrevivente.inventario)
        if not tem_agua:
            estado.sobrevivente.inventario.append(Item(nome="Água", quantidade=2))
    elif upgrade_info["name"] == "Oficina":
        estado.sobrevivente.xp += 1

    return f"Upgrade '{upgrade_info['name']}' instalado! Espaço restante: {r.espaco}."


def listar_acoes() -> list[dict]:
    return [
        {"id": "caçar", "nome": "Caçar Alimento", "tempo": 2, "atributo": "Mente", "pericia": "Sobrevivência"},
        {"id": "procurar_abrigo", "nome": "Procurar Abrigo Temporário", "tempo": 0.5, "atributo": "Mente", "pericia": "Investigação"},
        {"id": "procurar_refugio", "nome": "Procurar Novo Refúgio", "tempo": 5, "atributo": "Mente", "pericia": "Investigação"},
        {"id": "item_especifico", "nome": "Conseguir Item Específico", "tempo": 1, "atributo": "Mente", "pericia": "Investigação"},
        {"id": "item_aleatorio", "nome": "Conseguir Item Aleatório", "tempo": 1, "atributo": "", "pericia": ""},
        {"id": "interagir", "nome": "Interagir com Personagem", "tempo": 0.5, "atributo": "Espírito", "pericia": "Manipulação"},
        {"id": "voltar_refugio", "nome": "Voltar ao Refúgio", "tempo": 1, "atributo": "", "pericia": ""},
        {"id": "descansar", "nome": "Descansar (Passar a Noite)", "tempo": 8, "atributo": "", "pericia": ""},
    ]


def serializar_estado(estado: EstadoJogo) -> dict:
    return json.loads(estado.model_dump_json())


def carregar_estado(dados: dict) -> EstadoJogo:
    return EstadoJogo(**dados)
