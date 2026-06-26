<div align="center">

# 🔮 A HERANÇA DE CTHULHU

**Um RPG Solo de Sobrevivência Lovecraftiana — Terminal + LLM**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-000?logo=ollama&logoColor=white)](https://ollama.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

O fim chegou. Os Grandes Antigos despertaram. Arkham é agora um arquipélago de escombros, loucura e desespero. Você é um sobrevivente — caçando comida, improvisando abrigo, enfrentando criaturas que a sanidade não deveria testemunhar.

Este é um RPG solo baseado no sistema **SOLO10** e no livro *A Herança de Cthulhu* (101 Games), rodando diretamente no terminal. Opcionalmente, um LLM local via Ollama narra eventos, interpreta NPCs e escreve diários.

## Gameplay

```
   Hex Grid (axial)   Ações        Eventos        Combate
   ┌─────────────┐   ┌────────┐   ┌────────┐   ┌──────────┐
   │ NE  C.Nova  │   │ Caçar  │   │ Rolar  │   │ Atacar   │
   │ L   C.Velha │ → │ Itens  │ → │ Evento │ → │ Fugir    │
   │ SE  Porto   │   │ Interag│   │ Setor  │   │ Morrer   │
   └─────────────┘   └────────┘   └────────┘   └──────────┘
```

### Características

- **Mapa hexagonal** com 5 setores únicos (Cidade Nova, Cidade Velha, Centro Industrial, Porto, Ermos)
- **Cada setor tem características singulares** — dois hexágonos do mesmo tipo são diferentes entre si
- **Direção cardinal** ao navegar (N, NE, L, SE, S, SO, O, NO)
- **Ciclo dia/noite** — às 18h escurece e as hordas caçam
- **Gerenciamento de recursos** — fome, loucura, saúde, postura, vontade
- **Combate** — enfrente ou fuja de encontros violentos
- **Refúgio personalizável** — upgrades como Muralha, Horta, Torre de Vigia
- **Eventos aleatórios por setor** — cada setor tem sua própria tabela de eventos (d20)
- **LLM opcional** — narrativa rica, NPCs interpretados, Oráculo, Diário automático
- **Histórico persistente** — todas as ações ficam registradas com timestamp e local

## Pré-requisitos

- **Python 3.12+**
- **[Ollama](https://ollama.ai)** (opcional, para narrativa com IA)
- Modelo compatível (ex: `qwen2.5:1.5b`)

## Setup Rápido

```bash
# 1. Clone
git clone https://github.com/seu-usuario/heranca-de-cthulhu.git
cd rpg-criancas

# 2. Instalar dependências
pip install rich httpx pydantic

# 3. Modelo Ollama (opcional)
ollama pull qwen2.5:1.5b
```

## Como Jogar

```bash
# Modo padrão (sem IA)
python3 -m backend.heranca.cli

# Com narrativa via LLM
python3 -m backend.heranca.cli --llm

# Com modelo específico
python3 -m backend.heranca.cli --llm --model qwen2.5:1.5b
```

### Comandos durante o jogo

| Opção | Descrição |
|-------|-----------|
| `1` | Mover para outro setor |
| `2` | Ver status detalhado |
| `3-10` | Ações (Caçar, Itens, Interagir, etc.) |
| `?` | Ajuda |
| `Gerenciar Refúgio` | Instalar upgrades |
| `Salvar` | Salvar jogo |
| `Sair` | Encerrar partida |

Com `--llm` ativo:
| Opção | Descrição |
|-------|-----------|
| `Consultar o Oráculo` | Faça perguntas ao Oráculo |
| `Escrever no Diário` | Gera entrada narrativa do dia |

## Sistema de Combate

Ao encontrar inimigos, você pode:

1. **Atacar (Corpo a Corpo)** — rola Corpo + Combate Corporal
2. **Atacar (à Distância)** — rola Corpo + Combate a Distância (requer arma ranged)
3. **Fugir** — rola Corpo + Atletismo para escapar

Cada turno o inimigo revida. Combate continua até vitória, fuga ou morte.

## Mapa

```
            (-1,0) Centro Industrial
                \
    (0,-1) Ermos--(0,0) Cidade Nova--(1,0) Cidade Velha
                      \
                  (0,1) Porto
```

Coordenadas axiais com direções cardeais. O Refúgio inicial fica em Cidade Nova (0,0).

## Estrutura do Projeto

```
rpg-criancas/
├── backend/heranca/
│   ├── cli.py              # Interface de terminal (Rich)
│   ├── engine.py           # Motor do jogo (hex grid, combate, eventos)
│   ├── models.py           # Modelos Pydantic
│   ├── narrative.py        # LLM (Ollama) — narrativa, NPC, oráculo, diário
│   ├── data_loader.py      # Carregamento de dados JSON
│   └── data/               # Dados do jogo (setores, eventos, itens, etc.)
│       ├── sectors.json
│       ├── events/
│       ├── items.json
│       └── adversaries.json
├── docs/heranca-de-cthulhu/
│   ├── ROADMAP.md
│   └── SOLO10_LICENCA_ABERTA.md
└── README.md
```

## Licença

MIT. Baseado no sistema **SOLO10** (CC BY) e no livro *A Herança de Cthulhu* (101 Games).
