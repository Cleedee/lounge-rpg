<div align="center">

# 🔷 NEON SCRATCH LOUNGE

**Um RPG cyberpunk felino rodando localmente com LLM open-source**

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)](https://reactjs.org)
[![Ollama](https://img.shields.io/badge/Ollama-000?logo=ollama&logoColor=white)](https://ollama.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

Neo-Pawsburg, 2087. Gatos ciborgues lutam por território, chips e sobrevivência nas ruas encharcadas de néon. Este é um RPG de mesa single-player onde um LLM local (via Ollama) atua como mestre — narrando, descrevendo cenas e reagindo às suas ações.

## Projeto Original

Este é um **fork/adaptação local** do projeto original [neon-scratch-lounge](https://github.com/chaotictoejam/neon-scratch-lounge) por ChaoticToeJam.

O original foi escrito em **TypeScript** com infraestrutura **AWS** (Lambda + DynamoDB + Step Functions + EventBridge + CloudWatch + API Gateway). Esta versão reimplementa todo o backend em **Python** com **FastAPI + SQLite**, removendo dependências de nuvem e substituindo o modelo proprietário por LLMs open-source via [Ollama](https://ollama.ai).

Frontend React + Vite foi mantido do original (pasta `ui/`).

## Arquitetura

```
jogador → POST /action  →  FastAPI  →  lore_retriever (RAG local)
                                      →  dungeon_master  →  game_engine (8 tools)
                                                         →  Ollama (narrativa)
                                      →  SQLite (persistência)
```

### Modos de Jogo (DM_MODE)

| Modo | Descrição | Ideal para |
|---|---|---|
| `single_shot` (default) | Engine Python parseia a ação por keywords, executa as tools, e chama o LLM **uma única vez** para narrar os resultados. Rápido e confiável em CPU. | Modelos pequenos (0.5b–1.5b), CPU |
| `agentic` | LLM decide quais tools chamar em loop multi-turn (até 12 iterações), igual ao original da AWS. Requer modelo mais capaz. | GPU, modelos 7B+ |

Alternância via env var: `DM_MODE=agentic` ou `DM_MODE=single_shot`.

### Tools da Game Engine

- `roll-dice` — Rolagem de dados (d4 a d20) com bônus de atributo
- `apply-damage` — Dano/cura ao jogador
- `update-inventory` — Gerenciar inventário e CreditChips
- `award-xp` — Experiência e nível
- `update-location` — Navegação entre zonas
- `apply-effect` — Status effects
- `use-special-ability` — Habilidade especial da classe
- `update-quest-log` — Registro de missões

## Pré-requisitos

- **Python 3.12+**
- **[Ollama](https://ollama.ai)** rodando em segundo plano
- Um modelo de chat compatível (ex: `qwen2.5:0.5b`, `qwen2.5:1.5b`)
- Node.js 18+ (para o frontend)
- `nomic-embed-text` (para o RAG de lore)

## Setup Rápido

```bash
# 1. Clone
git clone https://github.com/seu-usuario/lounge-rpg.git
cd lounge-rpg

# 2. Backend
cd backend
pip install fastapi uvicorn httpx pydantic

# 3. Frontend
cd ../ui
npm install
cp .env.local.example .env.local  # ajuste se necessário

# 4. Modelos Ollama
ollama pull qwen2.5:0.5b
ollama pull nomic-embed-text
```

## Rodar

```bash
# Terminal 1: Backend
cd backend
uvicorn main:app --port 8001 --reload

# Terminal 2: Frontend
cd ui
npm run dev
```

Acessar frontend em `http://localhost:5173`.

## Configuração

Todas as opções são configuráveis via variáveis de ambiente:

| Variável | Default | Descrição |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | URL do Ollama |
| `OLLAMA_MODEL` | `qwen2.5:1.5b` | Modelo de chat |
| `DM_MODE` | `single_shot` | `single_shot` ou `agentic` |
| `LOCALE` | `pt-BR` | Idioma (`pt-BR` ou `en-US`) |
| `DATABASE_PATH` | `./data/neon_scratch.db` | Caminho do SQLite |

## Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/action` | Enviar ação do jogador |
| `GET` | `/action/status?turnId=` | Status de uma ação |
| `POST` | `/demo/inject-failure` | Injetar falha forçada (demo) |
| `POST` | `/demo/clear-failure` | Limpar falha forçada |
| `GET` | `/demo/logs?campaignId=` | Logs de turnos |

## Classes de Personagem

| Classe | HP | Atributo Principal | Habilidade Especial |
|---|---|---|---|
| TabbyWarrior | 120 | Força (8) | Nine Lives — revive com 1HP uma vez |
| SiameseMage | 70 | Arcano (9) | Laser Focus — 3x dano arcano (custa 10HP) |
| MaineCoonPaladin | 100 | Força (6) | Holy Hairball Shield — bloqueia 15 de dano |
| SphinxRogue | 80 | Agilidade/Stealth (9) | Sandstorm Vanish — invisibilidade 3 turnos |

## Zonas

NeonScratchLounge, ChromeAlley, RoombaCoreTower, NightMarket, SewersOfForgetfulness, IndustrialZone.

## Estrutura do Projeto

```
lounge-rpg/
├── backend/
│   ├── main.py              # FastAPI, rotas, fallback narrativo
│   ├── config.py            # Config centralizada (Ollama, modo, timeouts)
│   ├── models.py            # Pydantic models + constantes do jogo
│   ├── database.py          # SQLite (campanhas + turn_results)
│   ├── campaign_manager.py  # CRUD de campanhas
│   ├── dungeon_master.py    # Dispatcher: agentic ou single-shot
│   ├── game_engine.py       # 8 tools de jogo
│   ├── lore_retriever.py    # RAG por keyword scoring
│   ├── response_builder.py  # Montagem de resposta
│   ├── i18n.py              # Internacionalização
│   └── locales/
│       └── pt-BR.json       # Traduções pt-BR
├── ui/                      # Frontend React+Vite (original adaptado)
│   ├── src/
│   │   ├── components/      # Componentes React
│   │   ├── i18n/            # Traduções do frontend
│   │   └── ...
│   └── .env.local.example   # Template de configuração
├── lore/                    # JSONs de lore (classes, inimigos, itens, locais)
│   └── pt-BR/               # Versão traduzida
├── data/                    # Banco SQLite (criado em runtime, ignorado pelo git)
└── README.md
```

## Fallback

Se o Ollama estiver offline ou o modelo for muito lento, o sistema usa narrativas fallback pré-escritas — as mecânicas (dados, dano, inventário, locomoção) continuam funcionando normalmente.

## Licença

MIT. Este projeto é um fork adaptado do [neon-scratch-lounge](https://github.com/chaotictoejam/neon-scratch-lounge) original, mantendo a mesma licença.
