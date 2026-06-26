import json
import logging
from typing import Optional

logger = logging.getLogger("heranca.narrative")

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"
OLLAMA_TIMEOUT = 120
LLM_DISPONIVEL = False


def verificar_ollama() -> bool:
    global LLM_DISPONIVEL
    try:
        import httpx
        resp = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        model_name = OLLAMA_MODEL
        disponivel = any(
            m.get("name") == model_name or m.get("name", "").startswith(model_name)
            for m in models
        )
        LLM_DISPONIVEL = disponivel
        if not disponivel:
            logger.warning("Modelo '%s' não encontrado no Ollama. Modelos: %s",
                           model_name, [m.get("name") for m in models])
        return disponivel
    except Exception as e:
        LLM_DISPONIVEL = False
        logger.debug("Ollama não disponível: %s", e)
        return False


def _chamar_ollama(system_prompt: str, user_prompt: str, max_tokens: int = 300) -> Optional[str]:
    if not LLM_DISPONIVEL:
        return None
    try:
        import httpx
        payload = {
            "model": OLLAMA_MODEL,
            "system": system_prompt,
            "prompt": user_prompt,
            "options": {
                "temperature": 0.4,
                "max_tokens": max_tokens,
            },
            "stream": False,
        }
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        logger.debug("Erro ao chamar Ollama: %s", e)
        return None


SYSTEM_NARRADOR = """Você é o Narrador de A HERANÇA DE CTHULHU, um RPG de terror lovecraftiano e sobrevivência pós-apocalíptica.

REGRAS:
- Narre em português brasileiro, em segunda pessoa ("você").
- Tom: sombrio, atmosférico.
- MUITO CURTO: no máximo 3 frases. Uma ou duas linhas.
- NUNCA decida mecânicas (dano, cura, sucesso/falha de teste) — isso já foi resolvido pelo sistema.
- Apenas descreva a cena com base nos resultados recebidos.
- Incorpore o estado atual do personagem na narrativa."""

SYSTEM_NPC = """Você interpreta um NPC no mundo de A HERANÇA DE CTHULHU.

REGRAS:
- Responda EM PORTUGUÊS BRASILEIRO como o NPC, usando falas diretas entre aspas.
- MUITO CURTO: no máximo 2 falas curtas.
- NUNCA decida mecânicas. Apenas interprete."""

SYSTEM_ORACULO = """Você é um Oráculo para um RPG solo lovecraftiano.

REGRAS:
- Responda perguntas Sim/Não/Talvez com 1 frase de evidência.
- MUITO CURTO: no máximo 2 frases.
- Mantenha o tom de mistério."""

SYSTEM_DIARIO = """Você é um Sobrevivente escrevendo seu diário em um mundo devastado pelos Grandes Antigos.

REGRAS:
- Escreva EM PORTUGUÊS BRASILEIRO em primeira pessoa.
- Tom: cansado, humano.
- MUITO CURTO: no máximo 1 parágrafo curto (3-4 frases).
- Reflita os eventos do dia e o estado físico/mental do personagem."""


def narrar_evento(evento_titulo: str, descricao: str, resultado_teste: dict = None,
                  sucesso: bool = None, estado: dict = None, historico: str = None) -> str:
    contexto = f"Evento: {evento_titulo}\nDescrição: {descricao}\n"
    if resultado_teste:
        contexto += f"Teste: {'Sucesso' if resultado_teste.get('sucesso') else 'Falha'} (total: {resultado_teste.get('total')}, Bônus de Poder: {resultado_teste.get('bonus_poder')})\n"
    if sucesso is not None:
        contexto += f"Resultado: {'Sucesso' if sucesso else 'Falha'}\n"
    if estado:
        contexto += f"Estado do personagem: Saúde {estado.get('saude', '?')}/{estado.get('saude_max', '?')}, Fome {estado.get('fome', 0)}, Loucura {estado.get('loucura', 0)}\n"
    if historico:
        contexto += f"\n{historico}\n"

    resposta = _chamar_ollama(SYSTEM_NARRADOR, contexto, max_tokens=120)
    if resposta:
        return resposta
    return _fallback_evento(evento_titulo, descricao, resultado_teste, sucesso)


def _fallback_evento(titulo: str, descricao: str, teste: dict = None, sucesso: bool = None) -> str:
    texto = f"[bold]{titulo}[/]\n{descricao}"
    if teste:
        resultado = "✅ Sucesso" if sucesso else "❌ Falha"
        texto += f"\n\nTeste: {resultado} (rolagem {teste.get('total', '?')})"
    return texto


def interpretar_npc(npc_nome: str, npc_descricao: str,
                   postura_relativa: str = "Neutro",
                   intencao_jogador: str = "conversar",
                   estado: dict = None, historico: str = None) -> str:
    contexto = (
        f"NPC: {npc_nome}\n"
        f"Descrição: {npc_descricao}\n"
        f"Postura relativa ao jogador: {postura_relativa}\n"
        f"Intenção do jogador: {intencao_jogador}\n"
    )
    if estado:
        contexto += f"Local: {estado.get('setor', 'desconhecido')}, Hora: {estado.get('hora', '?')}:00\n"
    if historico:
        contexto += f"\n{historico}\n"

    resposta = _chamar_ollama(SYSTEM_NPC, contexto, max_tokens=100)
    if resposta:
        return resposta
    return f"[italic]{npc_nome} parece te avaliar, mas não diz nada de imediato.[/italic]"


def oraculo(pergunta: str, estado: dict = None, historico: str = None) -> str:
    contexto = f"Pergunta do jogador: {pergunta}\n"
    if estado:
        contexto += f"Contexto: setor {estado.get('setor', '?')}, dia {estado.get('dia', '?')}, hora {estado.get('hora', '?')}:00\n"
    if historico:
        contexto += f"\n{historico}\n"

    resposta = _chamar_ollama(SYSTEM_ORACULO, contexto, max_tokens=80)
    if resposta:
        return resposta
    return "O Oráculo permanece em silêncio. Você não encontra respostas claras."


def gerar_diario(eventos_do_dia: list[str], estado: dict = None, dia: int = 1, historico: str = None) -> str:
    contexto = f"Diário do Sobrevivente — Dia {dia}\n\nEventos do dia:\n"
    for ev in eventos_do_dia:
        contexto += f"- {ev}\n"
    if estado:
        contexto += (
            f"\nEstado: Saúde {estado.get('saude', '?')}/{estado.get('saude_max', '?')}, "
            f"Vontade {estado.get('vontade', '?')}/{estado.get('vontade_max', '?')}, "
            f"Fome {estado.get('fome', 0)}, Loucura {estado.get('loucura', 0)}\n"
        )

    resposta = _chamar_ollama(SYSTEM_DIARIO, contexto, max_tokens=150)
    if resposta:
        return resposta
    return f"*O diário do Dia {dia} está em branco. Você não teve energia para escrever.*"


def narrar_combate(arma: str, dano: int, alvo: str, resultado_teste: dict) -> str:
    contexto = (
        f"Ação: Ataque com {arma}\n"
        f"Resultado: {'Acertou' if resultado_teste.get('sucesso') else 'Errou'} "
        f"(rolagem {resultado_teste.get('total', '?')}, Bônus de Poder: {resultado_teste.get('bonus_poder', 0)})\n"
        f"Dano causado: {dano}\n"
        f"Alvo: {alvo}\n"
    )
    resposta = _chamar_ollama(SYSTEM_NARRADOR, contexto, max_tokens=100)
    if resposta:
        return resposta
    if resultado_teste.get("sucesso"):
        return f"Você ataca com {arma} e acerta {alvo}, causando {dano} de dano."
    return f"Você tenta atacar com {arma}, mas erra {alvo}."
