#!/usr/bin/env python3
import sys
import json
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.layout import Layout
from rich.text import Text
from rich import box

from backend.heranca.models import (
    EstadoJogo, Sobrevivente, Stats, Refugio, UpgradeRefugio,
    Arma, Armadura, Item, FaseDia, PERICIAS,
)
from backend.heranca.engine import (
    iniciar_estado, SETORES, TODAS_ARMAS, TODAS_ARMADURAS,
    setores_disponiveis, mover_setor, rolar_evento, resolver_evento,
    verificar_encontro_violento, gerar_encontro_violento,
    rolar_ataque_horda, passar_noite, processar_fome_diaria,
    ataque_ao_refugio, construir_upgrade, listar_acoes,
    testar, sofrer_dano, consumir_comida, avancar_hora,
    d10, d10_rolar, hex_chave, HexCoordenada, UPGRADES,
)

console = Console()
SAVE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
os.makedirs(SAVE_DIR, exist_ok=True)

USAR_LLM = False
LLM_DIARIO_ATIVO = False
DIARIO_DO_DIA: list[str] = []


def _setor_atual_info(estado: EstadoJogo):
    from backend.heranca.engine import hex_tipo, hex_chave
    tipo_id = hex_tipo(estado)
    setor = SETORES.get(tipo_id) if tipo_id else None
    chave = hex_chave(estado.setor_atual.q, estado.setor_atual.r)
    setor_hex = estado.mapa.get(chave)
    caract = setor_hex.caracteristica if setor_hex else ""
    nome = setor.nome if setor else tipo_id or chave
    if caract:
        nome += f" — {caract}"
    return nome, chave, setor


def cabecalho(estado: EstadoJogo):
    s = estado.sobrevivente
    r = estado.refugio
    setor_nome, chave, setor = _setor_atual_info(estado)

    grid = Table.grid(padding=(0, 2))
    grid.add_column()
    hora_int = int(estado.hora)
    minutos = int((estado.hora - hora_int) * 60)
    grid.add_row(
        f"[bold yellow]Dia {estado.dia}[/] | "
        f"[bold cyan]{estado.fase.value}[/] | "
        f"[bold]{hora_int:02d}:{minutos:02d}[/] | "
        f"[bold green]{setor_nome}[/] "
        f"[dim]({estado.setor_atual.q},{estado.setor_atual.r})[/]"
    )
    grid.add_row(
        f"[red]Saúde: {s.saude}/{s.stats.saude_max}[/] | "
        f"[blue]Postura: {s.postura}/{s.stats.postura_max}[/] | "
        f"[magenta]Vontade: {s.vontade}/{s.stats.vontade_max}[/]"
    )
    grid.add_row(
        f"[yellow]Fome: {'█' * s.fome_marcadores}{'░' * (s.stats.corpo - s.fome_marcadores)}[/] | "
        f"[red]Loucura: {'█' * s.loucura_marcadores}{'░' * (s.stats.mente - s.loucura_marcadores)}[/] | "
        f"[green]XP: {s.xp}[/]"
    )
    llm_status = "[green]LLM[/]" if USAR_LLM and LLM_DIARIO_ATIVO else "[dim]LLM[/]"
    grid.add_row(
        f"[white]Refúgio: {r.tipo} (Defesa: {r.defesa}/{r.defesa_max})[/] | "
        f"[white]Armas: {s.arma_equipada.nome if s.arma_equipada else 'Desarmado'}[/]"
    )
    grid.add_row(
        f"[dim]Dicas: ? para ajuda | LLM: {llm_status}[/dim]"
    )

    console.print(Panel(grid, title="A Herança de Cthulhu", border_style="cyan"))


def mostrar_menu(acoes: list[dict], titulo: str = "Ações Disponíveis") -> str:
    table = Table(title=titulo, box=box.ROUNDED)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Ação", style="white")
    table.add_column("Tempo", style="yellow")

    for i, acao in enumerate(acoes, 1):
        table.add_row(str(i), acao["nome"], f"{acao['tempo']}h" if acao['tempo'] >= 1 else f"{int(acao['tempo']*60)}min")
        if "descricao" in acao:
            table.add_row("", f"[dim]{acao['descricao']}[/dim]", "")

    console.print(table)
    return Prompt.ask("[cyan]Escolha[/]", default="1")


def criar_personagem() -> EstadoJogo:
    console.print(Panel.fit("[bold yellow]CRIAÇÃO DE PERSONAGEM[/]", border_style="yellow"))

    nome = Prompt.ask("[cyan]Nome do Sobrevivente[/]", default="Carter")

    console.print("\n[bold]Distribua 9 pontos entre os atributos (mínimo 1, máximo 5):[/]")
    stats = Stats()
    pontos = 9

    for attr_name, attr_key in [("Corpo", "corpo"), ("Mente", "mente"), ("Espírito", "espirito")]:
        while True:
            val = IntPrompt.ask(f"  [cyan]{attr_name}[/] (restam {pontos} pontos)", default=1)
            if val < 1 or val > 5:
                console.print("[red]Valor deve ser entre 1 e 5.[/]")
                continue
            if val > pontos + 1:
                console.print(f"[red]Você só tem {pontos + 1} pontos disponíveis (já tem 1).[/]")
                continue
            setattr(stats, attr_key, val)
            pontos -= (val - 1)
            break

    if pontos > 0:
        console.print(f"[yellow]Sobraram {pontos} pontos. Atribuindo ao Espírito.[/]")
        stats.espirito = min(5, stats.espirito + pontos)

    console.print(f"\n[bold]Atributos finais:[/] Corpo [cyan]{stats.corpo}[/], Mente [cyan]{stats.mente}[/], Espírito [cyan]{stats.espirito}[/]")
    console.print(f"Saúde: {stats.saude_max} | Postura: {stats.postura_max} | Vontade: {stats.vontade_max}")

    console.print("\n[bold]Escolha 5 Perícias das seguintes:[/]")
    pericias_escolhidas = []
    pericias_disp = list(PERICIAS)

    for _ in range(5):
        table = Table(box=box.SIMPLE)
        table.add_column("#", style="cyan", width=3)
        table.add_column("Perícia")
        for i, p in enumerate(pericias_disp, 1):
            table.add_row(str(i), p)
        console.print(table)

        escolha = IntPrompt.ask("[cyan]Escolha uma perícia[/]", default=1)
        if 1 <= escolha <= len(pericias_disp):
            p = pericias_disp.pop(escolha - 1)
            pericias_escolhidas.append(p)
            console.print(f"  → [green]{p} adquirida![/]")
        else:
            console.print("[red]Inválido.[/]")

    console.print("\n[bold]Escolha seu Refúgio base:[/]")
    refs = [
        ("Residência", "Escombros", 50, 5, 5),
        ("Câmara", "Subterrâneo", 70, 3, 5),
        ("Galpão", "Ruínas", 30, 7, 5),
        ("Morada", "Litoral", 50, 5, 5),
        ("Fazenda", "Ermo", 30, 9, 3),
    ]
    table = Table(box=box.ROUNDED)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Tipo")
    table.add_column("Setor")
    table.add_column("Defesa")
    table.add_column("Espaço")
    table.add_column("Tecnologia")
    for i, (tipo, setor, defs, esp, tec) in enumerate(refs, 1):
        table.add_row(str(i), tipo, setor, str(defs), str(esp), str(tec))
    console.print(table)
    ref_choice = IntPrompt.ask("[cyan]Escolha[/]", default=1) - 1
    tipo, setor, defs, esp, tec = refs[ref_choice]

    console.print("\n[bold]Escolha sua arma inicial:[/]")
    table = Table(box=box.SIMPLE)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Arma")
    table.add_column("Dano")
    table.add_column("Tipo")
    armas_disp = [a for a in TODAS_ARMAS if a.nome not in ("Desarmado",)]
    for i, a in enumerate(armas_disp[:12], 1):
        dano = f"Corpo+{a.dano_bonus}" if a.tipo != "explosive" else f"{a.dano_fixo} fixo"
        table.add_row(str(i), a.nome, dano, a.tipo)
    console.print(table)
    arma_choice = IntPrompt.ask("[cyan]Escolha[/]", default=1) - 1
    arma_escolhida = armas_disp[arma_choice]

    console.print("\n[bold]Escolha sua armadura inicial:[/]")
    armaduras_disp = TODAS_ARMADURAS
    table = Table(box=box.SIMPLE)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Armadura")
    table.add_column("Redução")
    for i, a in enumerate(armaduras_disp, 1):
        table.add_row(str(i), a.nome, str(a.reducao))
    console.print(table)
    arm_choice = IntPrompt.ask("[cyan]Escolha[/]", default=1) - 1
    armadura_escolhida = armaduras_disp[arm_choice]

    estado = iniciar_estado()
    estado.sobrevivente = Sobrevivente(
        nome=nome,
        stats=stats,
        pericias=pericias_escolhidas,
        saude=stats.saude_max,
        postura=stats.postura_max,
        vontade=stats.vontade_max,
        arma_equipada=arma_escolhida,
        armadura_equipada=armadura_escolhida,
        inventario=[Item(nome="Comida", quantidade=5 + d10())],
    )
    estado.refugio = Refugio(tipo=tipo, setor_id=setor, defesa=defs, defesa_max=defs,
                              espaco=esp, espaco_max=esp, tecnologia=tec, tecnologia_max=tec)

    console.print(f"\n[bold green]Sobrevivente {nome} criado![/]")
    return estado


def _setor_id_atual(estado):
    from backend.heranca.engine import hex_tipo
    return hex_tipo(estado) or "desconhecido"


def _registrar_acontecimento(estado: EstadoJogo, descricao: str):
    chave = hex_chave(estado.setor_atual.q, estado.setor_atual.r)
    setor_nome, _, _ = _setor_atual_info(estado)
    h_int = int(estado.hora)
    mins = int((estado.hora - h_int) * 60)
    entry = f"[Dia {estado.dia} {h_int:02d}:{mins:02d}] {setor_nome} ({chave}): {descricao}"
    estado.acontecimentos_registrados.append(entry)
    DIARIO_DO_DIA.append(descricao)


def _historico_recente(estado: EstadoJogo, n: int = 10) -> str:
    if not estado.acontecimentos_registrados:
        return ""
    recentes = estado.acontecimentos_registrados[-n:]
    return "Histórico recente:\n" + "\n".join(recentes)


def _narrativa_acao(estado, acao_id: str, resultado_teste: dict, setor_nome: str) -> str:
    if USAR_LLM:
        from backend.heranca.narrative import narrar_evento
        titulos = {
            "caçar": "Caçada nos Escombros",
            "procurar_abrigo": "Busca por Abrigo",
            "procurar_refugio": "Exploração de Novo Refúgio",
            "item_aleatorio": "Revirando os Escombros",
            "interagir": "Encontro com Estranho",
        }
        titulo = titulos.get(acao_id, "Ação")
        desc = _acoes_desc.get(acao_id, "Você realiza uma ação no setor.")
        s = estado.sobrevivente
        historico = _historico_recente(estado)
        r = narrar_evento(titulo, desc, resultado_teste, resultado_teste.get("sucesso", False),
                          {"saude": s.saude, "saude_max": s.stats.saude_max,
                           "fome": s.fome_marcadores, "loucura": s.loucura_marcadores},
                          historico)
        if r and not r.startswith("[bold]"):
            return r
    return ""


_acoes_desc = {
    "caçar": "Você vasculha o setor em busca de comida, revirando escombros e armadilhas esquecidas.",
    "procurar_abrigo": "Você procura um local seguro para descansar e se proteger.",
    "procurar_refugio": "Você explora o setor em busca de um novo Refúgio permanente.",
    "item_aleatorio": "Você revira os escombros em busca de itens úteis.",
    "interagir": "Você procura por outros sobreviventes no setor. Role Mente (Investigação). Sucesso: um novo sobrevivente se junta a você.",
    "voltar_refugio": "Você retorna ao seu Refúgio.",
    "interagir_personagem": "Você conversa com uma personagem conhecida. Use Espírito (Manipulação) ou consulte o Oráculo.",
}


def executar_acao(estado: EstadoJogo, acao_id: str) -> str:
    global DIARIO_DO_DIA
    from backend.heranca.engine import hex_info
    setor_info = hex_info(estado)
    setor_nome = setor_info.nome if setor_info else _setor_id_atual(estado)

    if acao_id == "caçar":
        tempo = 1 if setor_info and setor_info.perigo >= 3 else 2
        avancar_hora(estado, tempo)
        r = testar(estado, "Mente", "Sobrevivência")
        llm_msg = _narrativa_acao(estado, "caçar", r, setor_nome)
        if llm_msg:
            return llm_msg
        if r["sucesso"]:
            qtd = d10()
            estado.sobrevivente.inventario.append(Item(nome="Comida", quantidade=qtd))
            _registrar_acontecimento(estado, f"Cacei e encontrei {qtd} unidades de comida.")
            return f"[green]✓[/] Caçada em {setor_nome} — Você encontrou {qtd} unidades de comida. (rolagem {r['total']})"
        _registrar_acontecimento(estado, "Tentei caçar mas não encontrei nada.")
        return f"[yellow]✗[/] Caçada em {setor_nome} — Nada encontrado. Os recursos estão escassos. (rolagem {r['total']})"

    elif acao_id == "procurar_abrigo":
        avancar_hora(estado, 0.5)
        r = testar(estado, "Mente", "Investigação")
        llm_msg = _narrativa_acao(estado, "procurar_abrigo", r, setor_nome)
        if llm_msg:
            return llm_msg
        if r["sucesso"]:
            _registrar_acontecimento(estado, "Encontrei um abrigo temporário para descansar.")
            return f"[green]✓[/] Abrigo encontrado em {setor_nome}! (rolagem {r['total']})"
        return f"[yellow]✗[/] Nenhum abrigo seguro em {setor_nome}. (rolagem {r['total']})"

    elif acao_id == "procurar_refugio":
        avancar_hora(estado, 5)
        r = testar(estado, "Mente", "Investigação")
        llm_msg = _narrativa_acao(estado, "procurar_refugio", r, setor_nome)
        if llm_msg:
            return llm_msg
        if r["sucesso"]:
            _registrar_acontecimento(estado, "Estabeleci um novo Refúgio.")
            return f"[green]✓[/] Novo Refúgio estabelecido em {setor_nome}! (rolagem {r['total']})"
        return f"[yellow]✗[/] Nenhum local adequado para Refúgio em {setor_nome}. (rolagem {r['total']})"

    elif acao_id == "item_aleatorio":
        avancar_hora(estado, 1)
        r = d10_rolar()
        if r <= 1 or r == 5:
            enc = gerar_encontro_violento(estado)
            _registrar_acontecimento(estado, f"Encontrei {enc['adversario']['name']} enquanto procurava por itens.")
            resultado = menu_combate(estado, enc)
            if resultado == "vitoria":
                return "[green]✓ Após vencer o combate, você continua procurando...[/]"
            elif resultado == "fuga":
                return "[yellow]✗ Você fugiu do combate.[/]"
            return "[red]☠ Você morreu no combate.[/]"
        tipos = {2: "Arma/Armadura", 3: "Equipamento", 4: "Recurso", 6: "Equipamento", 7: "Recurso", 8: "Veículo", 9: "Veículo", 0: "Artefato"}
        tipo = tipos.get(r, 'desconhecido')
        _registrar_acontecimento(estado, f"Encontrei {tipo} entre os escombros.")
        return f"[green]✓[/] Você encontrou: {tipo} em {setor_nome}."

    elif acao_id == "interagir":
        tempo = 1 if setor_info and setor_info.perigo >= 3 else 0.5
        avancar_hora(estado, tempo)
        r = testar(estado, "Mente", "Investigação")
        if r["sucesso"]:
            import random
            nomes = ["Elias", "Carla", "Jorge", "Mara", "Tadeu", "Isabel", "Ruy", "Lia"]
            nome = random.choice(nomes)
            _registrar_acontecimento(estado, f"Encontrei {nome}, outro sobrevivente, que decidiu se juntar a mim.")
            return f"[green]✓[/] Você encontrou [bold]{nome}[/], um sobrevivente que decide se juntar a você! (rolagem {r['total']})"
        _registrar_acontecimento(estado, "Tentei encontrar outros sobreviventes, mas não encontrei ninguém.")
        return f"[yellow]✗[/] Você não encontrou ninguém em {setor_nome}. (rolagem {r['total']})"

    elif acao_id == "interagir_personagem":
        avancar_hora(estado, 0.5)
        if USAR_LLM:
            from backend.heranca.narrative import interpretar_npc
            estado_dict = {"setor": _setor_id_atual(estado), "hora": int(estado.hora), "minutos": int((estado.hora - int(estado.hora)) * 60), "saude": estado.sobrevivente.saude}
            hist = _historico_recente(estado)
            fala = interpretar_npc("Um conhecido", "Um sobrevivente que você já encontrou antes", "Neutro", "conversar", estado_dict, hist)
            _registrar_acontecimento(estado, "Conversei com uma personagem conhecida.")
            return fala
        r = testar(estado, "Espírito", "Manipulação")
        _registrar_acontecimento(estado, f"Interagi com uma personagem: {'sucesso' if r['sucesso'] else 'não rendeu'}.")
        return f"[green]✓[/] Conversa produtiva. (rolagem {r['total']})" if r["sucesso"] else f"[yellow]✗[/] A conversa não rendeu. (rolagem {r['total']})"

    elif acao_id == "oraculo":
        if not USAR_LLM:
            return "Oráculo disponível apenas com LLM ativo."
        from backend.heranca.narrative import oraculo
        pergunta = Prompt.ask("[cyan]O que você pergunta ao Oráculo?[/]")
        if not pergunta:
            return "Você não fez pergunta alguma."
        estado_dict = {"setor": _setor_id_atual(estado), "dia": estado.dia, "hora": int(estado.hora), "minutos": int((estado.hora - int(estado.hora)) * 60)}
        hist = _historico_recente(estado)
        resposta = oraculo(pergunta, estado_dict, hist)
        _registrar_acontecimento(estado, f"Consultei o Oráculo sobre: {pergunta}")
        return resposta

    elif acao_id == "diario":
        if not USAR_LLM or not LLM_DIARIO_ATIVO:
            return "Diário disponível apenas com LLM ativo."
        from backend.heranca.narrative import gerar_diario
        if not DIARIO_DO_DIA:
            return "Nada aconteceu hoje ainda para registrar."
        s = estado.sobrevivente
        estado_dict = {
            "saude": s.saude, "saude_max": s.stats.saude_max,
            "vontade": s.vontade, "vontade_max": s.stats.vontade_max,
            "fome": s.fome_marcadores, "loucura": s.loucura_marcadores,
        }
        hist = _historico_recente(estado)
        entrada = gerar_diario(DIARIO_DO_DIA, estado_dict, estado.dia, hist)
        return entrada

    elif acao_id == "voltar_refugio":
        if not estado.refugio.setor_id:
            return "[yellow]Você não tem um Refúgio estabelecido.[/]"
        q_str, r_str = estado.refugio.setor_id.split(",")
        q_ref, r_ref = int(q_str), int(r_str)
        if estado.setor_atual.q == q_ref and estado.setor_atual.r == r_ref:
            return "[green]✓[/] Você já está no seu Refúgio."
        dist = abs(estado.setor_atual.q - q_ref) + abs(estado.setor_atual.r - r_ref)
        horas = max(1, dist * 2)
        estado.setor_atual = HexCoordenada(q=q_ref, r=r_ref)
        avancar_hora(estado, horas)
        _registrar_acontecimento(estado, f"Voltei ao Refúgio ({q_ref},{r_ref}).")
        return f"[green]✓[/] Você retorna ao seu Refúgio ({q_ref},{r_ref}). ({horas}h de viagem)"

    elif acao_id == "descansar":
        console.print("[yellow]Você se prepara para passar a noite...[/]")
        resultado = passar_noite(estado, no_refugio=True)

        if USAR_LLM and LLM_DIARIO_ATIVO and DIARIO_DO_DIA:
            from backend.heranca.narrative import gerar_diario
            s = estado.sobrevivente
            estado_dict = {
                "saude": s.saude, "saude_max": s.stats.saude_max,
                "vontade": s.vontade, "vontade_max": s.stats.vontade_max,
                "fome": s.fome_marcadores, "loucura": s.loucura_marcadores,
            }
            hist = _historico_recente(estado)
            entrada = gerar_diario(DIARIO_DO_DIA, estado_dict, estado.dia - 1, hist)
            console.print(Panel(entrada, title=f"[yellow]Diário — Dia {estado.dia - 1}[/]", border_style="yellow"))
            DIARIO_DO_DIA.clear()

        msg = resultado["msg"]
        if resultado.get("horda"):
            horda_info = resultado["horda"]
            msg += f"\n[red]☠ HORDA: {horda_info.descricao}[/]"
            r_ataque = ataque_ao_refugio(estado, horda_info)
            msg += f"\n{r_ataque['resultado']}"
        msg += "\n[green]☀ Você acordou! Novo dia começa.[/]"
        return msg

    return f"Ação '{acao_id}' executada em {setor_nome}."


def loop_jogo(estado: EstadoJogo):
    while not estado.encerrado:
        console.clear()
        cabecalho(estado)

        setor_nome, chave, setor = _setor_atual_info(estado)
        if setor:
            console.print(f"[dim]{setor.descricao}[/dim]")
            destinos = setores_disponiveis(estado)
            if destinos:
                cons = ", ".join(f"[cyan]{sigla}[/] {nome}" for _, _, nome, sigla, _ in destinos)
                console.print(f"[dim]Conexões: {cons}[/dim]")

        console.print("")

        if estado.fase != FaseDia.NOITE:
            acoes = listar_acoes()
            acoes.insert(0, {"id": "mover", "nome": "Mover para outro setor", "tempo": 1})
            acoes.insert(0, {"id": "status", "nome": "Ver status detalhado", "tempo": 0})
            acoes.append({"id": "upgrade", "nome": "Gerenciar Refúgio", "tempo": 0})
            acoes.append({"id": "salvar", "nome": "Salvar jogo", "tempo": 0})
            if USAR_LLM:
                acoes.append({"id": "oraculo", "nome": "Consultar o Oráculo (LLM)", "tempo": 0})
                acoes.append({"id": "diario", "nome": "Escrever no Diário (LLM)", "tempo": 0})
            acoes.append({"id": "sair", "nome": "Encerrar partida", "tempo": 0})

            escolha = mostrar_menu(acoes, f"Ações - {setor.nome if setor else ''}")
            if escolha.lower() == "?":
                console.print(Panel(
                    "[bold]Dicas de jogo:[/]\n"
                    "- Role eventos visitando setores e realizando ações\n"
                    "- Gerencie sua fome: caçar comida é essencial\n"
                    "- Volte ao Refúgio antes de anoitecer (18:00)\n"
                    "- Melhore seu Refúgio com upgrades\n"
                    "- Com LLM ativo: Oráculo e Diário disponíveis",
                    border_style="cyan"
                ))
                Prompt.ask("[dim]Enter para continuar[/]")
                continue
            try:
                idx = int(escolha) - 1
                if 0 <= idx < len(acoes):
                    acao = acoes[idx]
                    if acao["id"] == "sair":
                        if Prompt.ask("[red]Tem certeza?[/]", choices=["s", "n"], default="n") == "s":
                            estado.encerrado = True
                        continue
                    elif acao["id"] == "salvar":
                        salvar_jogo(estado)
                        continue
                    elif acao["id"] == "status":
                        mostrar_status(estado)
                        Prompt.ask("[dim]Enter para continuar[/]")
                        continue
                    elif acao["id"] == "upgrade":
                        menu_upgrade(estado)
                        continue
                    elif acao["id"] == "mover":
                        menu_mover(estado)
                        continue
                    else:
                        console.print(f"\n[bold]Ação: {acao['nome']}[/]")
                        msg = executar_acao(estado, acao["id"])
                        console.print(msg)
                        from backend.heranca.engine import rolar_evento, resolver_evento, verificar_encontro_violento, gerar_encontro_violento
                        evento = rolar_evento(estado)
                        if evento:
                            resultado = resolver_evento(estado, evento)
                            sucesso = resultado.get("sucesso")
                            status = "[green]Sucesso[/]" if sucesso else "[red]Falha[/]" if sucesso is False else ""
                            console.print(Panel(
                                f"[bold]{evento.titulo}[/]\n{evento.descricao}\n"
                                + (f"\nTeste: {status} (rolagem {resultado['rolagem_teste']['total']})" if resultado.get('rolagem_teste') else ""),
                                border_style="cyan" if sucesso else "red" if sucesso is False else "blue"
                            ))
                        if verificar_encontro_violento(estado):
                            encontro = gerar_encontro_violento(estado)
                            if encontro:
                                estado.encontros_hoje += 1
                                resultado_combate = menu_combate(estado, encontro)
                                if resultado_combate == "morte":
                                    break
                        Prompt.ask("[dim]Enter para continuar[/]")
                else:
                    console.print("[red]Opção inválida[/]")
            except ValueError:
                console.print("[red]Número inválido[/]")
        else:
            console.print("[bold red]Está escuro. As hordas dos Grandes Antigos caçam à noite![/]")
            no_ref = estado.refugio.setor_id == hex_chave(estado.setor_atual.q, estado.setor_atual.r)
            if not no_ref:
                console.print("[yellow]Você está longe do seu Refúgio...[/]")
            if Prompt.ask("[yellow]Dormir e passar a noite?[/]", choices=["s", "n"], default="s") == "s":
                resultado = passar_noite(estado, no_refugio=no_ref)
                console.print(resultado["msg"])
                if resultado.get("horda"):
                    horda_info = resultado["horda"]
                    console.print(f"[red]HORDA: {horda_info.descricao}[/]")
                    if no_ref:
                        r_atq = ataque_ao_refugio(estado, horda_info)
                        console.print(r_atq["resultado"])
                    else:
                        console.print("[red]Sem refúgio para proteger — a horda passa por você![/]")
                console.print("[green]Dia amanheceu![/]")
                Prompt.ask("[dim]Enter para continuar[/]")
            else:
                resultado = passar_noite(estado, no_refugio=False)
                console.print(resultado["msg"])
                Prompt.ask("[dim]Enter para continuar[/]")

        if estado.fase != FaseDia.NOITE and estado.hora >= 18:
            estado.fase = FaseDia.NOITE

        if estado.fase != FaseDia.NOITE:
            if verificar_encontro_violento(estado):
                encontro = gerar_encontro_violento(estado)
                if encontro:
                    desc = encontro['descricao']
                    if USAR_LLM:
                        from backend.heranca.narrative import narrar_combate
                        adv = encontro['adversario']
                        resultado_teste = {"sucesso": False, "total": 0, "bonus_poder": 0}
                        llm_desc = narrar_combate(
                            estado.sobrevivente.arma_equipada.nome if estado.sobrevivente.arma_equipada else "mãos",
                            0, adv['name'], resultado_teste
                        )
                        if llm_desc and not llm_desc.startswith("[bold]"):
                            desc = llm_desc
                    console.print()
                    console.print(Panel(f"[bold red]ENCONTRO VIOLENTO![/]\n{desc}",
                                        border_style="red"))
                    estado.encontros_hoje += 1

        if estado.encerrado and Prompt.ask("[red]Deseja continuar mesmo assim?[/]", choices=["s", "n"], default="n") != "s":
            break

    if estado.causa_morte:
        console.print(Panel(f"[bold red]FIM DE JOGO[/]\n{estado.sobrevivente.nome} morreu por: {estado.causa_morte}",
                            border_style="red"))
    else:
        console.print("[yellow]Partida encerrada.[/]")


def menu_combate(estado: EstadoJogo, encontro: dict) -> str:
    from backend.heranca.engine import atacar_adversario, reagir_adversario, sofrer_dano, testar
    adv = encontro['adversario']
    qtd = encontro['quantidade']
    hp_individual = adv['stats']['saude']
    hp_total = hp_individual * qtd
    dano_acumulado = 0

    console.print(Panel(
        f"[bold red]ENCONTRO VIOLENTO![/]\n"
        f"{qtd}x [bold]{adv['name']}[/]: {adv['description']}\n"
        f"[yellow]HP total: {hp_total}[/]",
        border_style="red"
    ))

    while hp_total - dano_acumulado > 0:
        s = estado.sobrevivente
        if s.saude <= 0:
            estado.encerrado = True
            estado.causa_morte = f"Morto por {adv['name']}"
            console.print("[bold red]VOCÊ MORREU![/]")
            return "morte"
        hp_rest = hp_total - dano_acumulado
        console.print(f"\n[red]Sua Saúde: {s.saude}/{s.stats.saude_max}[/] | "
                      f"[blue]Postura: {s.postura}/{s.stats.postura_max}[/]")
        console.print(f"[yellow]Inimigo: {qtd}x {adv['name']} — HP {hp_rest}/{hp_total}[/]")

        console.print("[bold]1.[/] Atacar (Corpo a Corpo)")
        console.print("[bold]2.[/] Atacar (à Distância)")
        console.print("[bold]3.[/] Fugir")
        escolha = Prompt.ask("[bold red]O que fazer?[/]", choices=["1", "2", "3"], default="1")

        dano = 0
        if escolha == "1":
            r_atq = atacar_adversario(estado, adv, "corporal")
            dano = r_atq["dano"]
            dano_acumulado += dano
            console.print(f"[green]✓[/] {r_atq['arma']} — causa {dano} de dano! (rolagem {r_atq['rolagem']['total']})")
        elif escolha == "2":
            r_atq = atacar_adversario(estado, adv, "distancia")
            if r_atq.get("erro"):
                console.print(f"[red]{r_atq['erro']}[/]")
                continue
            dano = r_atq["dano"]
            dano_acumulado += dano
            console.print(f"[green]✓[/] {r_atq['arma']} — causa {dano} de dano! (rolagem {r_atq['rolagem']['total']})")
        elif escolha == "3":
            r_fuga = testar(estado, "Corpo", "Atletismo")
            console.print(f"[yellow]Fugir: {'Sucesso' if r_fuga['sucesso'] else 'Falha'} (rolagem {r_fuga['total']})[/]")
            if r_fuga["sucesso"]:
                console.print("[green]✓ Você conseguiu fugir![/]")
                _registrar_acontecimento(estado, f"Fugi de {qtd}x {adv['name']}.")
                return "fuga"
            console.print("[red]✗ Não conseguiu escapar![/]")
            r_reacao = reagir_adversario(adv, 0)
            sofrer_dano(estado, r_reacao["dano"])
            console.print(f"[red]✗[/] {r_reacao['descricao']}")
            if s.saude <= 0:
                estado.encerrado = True
                estado.causa_morte = f"Morto por {adv['name']}"
                console.print("[bold red]VOCÊ MORREU![/]")
                return "morte"
            continue

        if hp_total - dano_acumulado <= 0:
            console.print(f"[bold green]VITÓRIA![/] {qtd}x {adv['name']} derrotado(s)!")
            _registrar_acontecimento(estado, f"Derrotei {qtd}x {adv['name']} em combate.")
            return "vitoria"

        r_reacao = reagir_adversario(adv, dano)
        sofrer_dano(estado, r_reacao["dano"])
        console.print(f"[red]✗[/] {r_reacao['descricao']}")

        if s.saude <= 0:
            estado.encerrado = True
            estado.causa_morte = f"Morto por {adv['name']}"
            console.print("[bold red]VOCÊ MORREU![/]")
            return "morte"

    return "vitoria"


def menu_mover(estado: EstadoJogo):
    destinos = setores_disponiveis(estado)
    if not destinos:
        console.print("[red]Nenhum destino disponível.[/]")
        return

    table = Table(title="Destinos", box=box.ROUNDED)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Direção", style="cyan")
    table.add_column("Setor")
    table.add_column("Característica")
    table.add_column("Perigo")
    for i, (q, r, nome, sigla, caract) in enumerate(destinos, 1):
        setor_hex = estado.mapa.get(hex_chave(q, r))
        s = SETORES.get(setor_hex.tipo) if setor_hex else None
        perigo_str = "★" * s.perigo + "☆" * (5 - s.perigo) if s else "?"
        table.add_row(str(i), f"[bold]{sigla}[/]", nome, f"[dim]{caract}[/dim]", perigo_str)
    console.print(table)

    escolha = IntPrompt.ask("[cyan]Para onde ir?[/]", default=1)
    if 1 <= escolha <= len(destinos):
        q, r, nome, sigla, caract = destinos[escolha - 1]
        veiculo = Prompt.ask("[cyan]Usar veículo?[/]", choices=["s", "n"], default="n") == "s"
        msg = mover_setor(estado, q, r, veiculo)
        console.print(f"\n[green]{msg}[/]")
        from backend.heranca.engine import hex_info
        _registrar_acontecimento(estado, f"Me movi para {sigla} — {nome} ({caract}).")
        setor_dest = hex_info(estado)
        if setor_dest:
            console.print()
            console.print(Panel(
                f"[bold yellow]{setor_dest.nome}[/] — [dim]{caract}[/dim]\n"
                f"[dim]{setor_dest.descricao}[/dim]\n"
                f"\n[cyan]Perigo: {'★' * setor_dest.perigo}{'☆' * (5 - setor_dest.perigo)}[/]",
                border_style="yellow"
            ))
        Prompt.ask("[dim]Enter para continuar[/]")


def menu_upgrade(estado: EstadoJogo):
    r = estado.refugio
    console.print(Panel(f"[bold]Refúgio: {r.tipo}[/]\nDefesa: {r.defesa}/{r.defesa_max} | Espaço: {r.espaco}/{r.espaco_max} | Tecnologia: {r.tecnologia}/{r.tecnologia_max}",
                        border_style="blue"))
    upgrades_instalados = [u for u in r.upgrades if u.ativo]
    if upgrades_instalados:
        console.print("[bold]Upgrades instalados:[/] " + ", ".join(u.nome for u in upgrades_instalados))


    table = Table(title="Upgrades Disponíveis", box=box.SIMPLE)
    table.add_column("#", style="cyan", width=3)
    table.add_column("Upgrade")
    table.add_column("Efeito")
    for i, u in enumerate(UPGRADES, 1):
        table.add_row(str(i), u["name"], u["effect"])
    console.print(table)

    escolha = Prompt.ask("[cyan]Instalar qual? (ou 0 para voltar)[/]", default="0")
    try:
        idx = int(escolha) - 1
        if 0 <= idx < len(UPGRADES):
            msg = construir_upgrade(estado, UPGRADES[idx]["name"])
            console.print(f"[yellow]{msg}[/]")
    except ValueError:
        pass
    Prompt.ask("[dim]Enter para voltar[/]")


def mostrar_status(estado: EstadoJogo):
    s = estado.sobrevivente
    r = estado.refugio
    setor_nome, chave, setor = _setor_atual_info(estado)

    grid = Table.grid(padding=(0, 1))
    grid.add_column(style="bold cyan")
    grid.add_column(style="white")

    grid.add_row("Nome", s.nome)
    grid.add_row("Dia", str(estado.dia))
    h_int = int(estado.hora)
    h_min = int((estado.hora - h_int) * 60)
    grid.add_row("Hora", f"{h_int:02d}:{h_min:02d}")
    grid.add_row("Fase", estado.fase.value)
    grid.add_row("Setor", f"{setor_nome} ({chave})")
    grid.add_row("")
    grid.add_row("Atributos", f"Corpo {s.stats.corpo} | Mente {s.stats.mente} | Espírito {s.stats.espirito}")
    grid.add_row("Perícias", ", ".join(s.pericias) if s.pericias else "Nenhuma")
    grid.add_row("")
    grid.add_row("Saúde", f"{s.saude}/{s.stats.saude_max}")
    grid.add_row("Postura", f"{s.postura}/{s.stats.postura_max}")
    grid.add_row("Vontade", f"{s.vontade}/{s.stats.vontade_max}")
    grid.add_row("")
    grid.add_row("Fome", f"{s.fome_marcadores} / crítico {s.stats.corpo} / max {s.stats.saude_max}")
    grid.add_row("Loucura", f"{s.loucura_marcadores} / crítico {s.stats.mente} / max {s.stats.vontade_max}")
    grid.add_row("Experiência", f"{s.xp} XP")
    grid.add_row("")
    grid.add_row("Arma", s.arma_equipada.nome if s.arma_equipada else "Desarmado")
    grid.add_row("Armadura", s.armadura_equipada.nome if s.armadura_equipada else "Nenhuma")
    grid.add_row("")
    grid.add_row("Refúgio", f"{r.tipo} (Defesa {r.defesa}/{r.defesa_max})")
    grid.add_row("Upgrades", ", ".join(u.nome for u in r.upgrades if u.ativo) or "Nenhum")
    if s.inventario:
        inv_text = "; ".join(f"{i.nome} x{i.quantidade}" if i.quantidade > 1 else i.nome for i in s.inventario)
        grid.add_row("Inventário", inv_text)

    console.print(Panel(grid, title="Status do Sobrevivente", border_style="green"))


def salvar_jogo(estado: EstadoJogo):
    dados = estado.model_dump()
    nome = estado.sobrevivente.nome.lower().replace(" ", "_")
    path = os.path.join(SAVE_DIR, f"save_{nome}.json")
    with open(path, "w") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    console.print(f"[green]Jogo salvo em {path}[/]")


def carregar_jogo(path: str) -> EstadoJogo | None:
    try:
        with open(path) as f:
            dados = json.load(f)
        return EstadoJogo(**dados)
    except Exception as e:
        console.print(f"[red]Erro ao carregar: {e}[/]")
        return None


def main():
    global USAR_LLM, LLM_DIARIO_ATIVO
    import argparse
    parser = argparse.ArgumentParser(description="A Herança de Cthulhu — RPG Solo CLI")
    parser.add_argument("--llm", action="store_true", help="Ativar narrativa via LLM (Ollama)")
    parser.add_argument("--model", default="qwen2.5:1.5b", help="Modelo Ollama (padrão: qwen2.5:1.5b)")
    args = parser.parse_args()

    console.clear()
    console.print(Panel.fit(
        "[bold yellow]A HERANÇA DE CTHULHU[/]\n"
        "[cyan]Um RPG Solo de Sobrevivência Lovecraftiana[/]\n"
        "[dim]Baseado no sistema SOLO10 (CC BY) e no livro A Herança de Cthulhu (101 Games)[/dim]",
        border_style="yellow"
    ))

    if args.llm:
        from backend.heranca.narrative import verificar_ollama
        if verificar_ollama():
            USAR_LLM = True
            LLM_DIARIO_ATIVO = True
            console.print("[green]✓ LLM conectado via Ollama[/]")
        else:
            USAR_LLM = False
            console.print("[yellow]✗ Ollama não disponível. Continuando sem LLM.[/]")
    else:
        console.print("[dim]LLM desligado. Use --llm para ativar narrativa com IA.[/]")

    saves = sorted(Path(SAVE_DIR).glob("save_*.json"))
    if saves:
        console.print("\n[bold]Saves encontrados:[/]")
        for i, sv in enumerate(saves, 1):
            console.print(f"  {i}. {sv.stem.replace('save_', '')}")
        console.print(f"  N. Novo jogo")
        escolha = Prompt.ask("[cyan]Carregar save?[/]", default="N")
        if escolha.isdigit():
            idx = int(escolha) - 1
            if 0 <= idx < len(saves):
                estado = carregar_jogo(str(saves[idx]))
                if estado:
                    console.print(f"[green]Save carregado![/]")
                    loop_jogo(estado)
                    return

    estado = criar_personagem()
    loop_jogo(estado)

    if not estado.encerrado:
        salvar_jogo(estado)

    console.print("[yellow]Até a próxima, Sobrevivente.[/]")


if __name__ == "__main__":
    main()
