# Neon Scratch Lounge — AGENTS.md

Este arquivo documenta as convenções e a arquitetura do projeto para assistentes de IA.

## Projeto

RPG single-player cyberpunk felino ("NEON SCRATCH LOUNGE"). O backend roda localmente com FastAPI + SQLite + Ollama (LLM open-source). O frontend é React 18 + TypeScript + Vite + Tailwind.

## Estrutura

```
├── backend/           # Python FastAPI
│   ├── main.py        # Rotas da API, FastAPI app
│   ├── config.py      # Config via env vars
│   ├── models.py      # Pydantic models + constantes do jogo
│   ├── database.py    # SQLite (WAL mode)
│   ├── campaign_manager.py
│   ├── dungeon_master.py    # Dispatcher do LLM (agentic | single_shot)
│   ├── game_engine.py       # Implementação das ferramentas de jogo
│   ├── lore_retriever.py    # RAG via keyword overlap em JSONs locais
│   ├── response_builder.py
│   ├── i18n.py + locales/   # Internacionalização (pt-BR, en)
│   └── requirements.txt     # fastapi, uvicorn, httpx, pydantic
├── ui/                # React + Vite + TypeScript + Tailwind
│   └── src/
│       ├── components/
│       │   ├── ClassSelector/   # ClassCard, modals
│       │   ├── GamePanel/       # HUD, narrativa, dados, combate, inventário, input
│       │   └── MechanicsPanel/  # WorkflowTrace, LogStream, MetricsStrip
│       ├── context/     # GameContext + MechanicsContext (useReducer)
│       ├── hooks/       # useApi, useTypewriter, useDiceAnimation, useWorkflowAnimation
│       ├── types/       # Tipos TypeScript + constantes
│       ├── utils/       # api.ts, formatters.ts, uuid.ts
│       └── i18n/        # Traduções pt-BR
├── lore/               # JSON de classes, inimigos, itens, locais (EN + pt-BR)
├── data/               # SQLite DB + saves
├── docs/               # PDF + páginas extraídas (Herança de Cthulhu)
└── saves/              # Vazio (reservado)
```

## Stack

| Camada     | Tecnologia                           |
|------------|--------------------------------------|
| Frontend   | React 18, TypeScript 5.5, Vite 5.4, Tailwind 3.4 |
| Backend    | Python 3.12+, FastAPI, Pydantic v2, httpx |
| Banco      | SQLite3 (stdlib, WAL mode)           |
| LLM        | Ollama (localhost:11434, model: mistral:7b) |
| RAG        | Keyword overlap scoring sobre JSONs locais |

## Convenções de Código

### Geral
- Sempre verificar package.json/requirements.txt antes de adicionar dependências
- Sempre rodar `npm run build` no frontend para type-check após alterações
- Sempre verificar `git diff` e `git status` antes de commits
- Commits em português brasileiro, formato: `Verbo no presente + descrição curta`

### Frontend
- **Componentes**: PascalCase, `export function Nome()` (named exports)
- **Hooks**: `use*` camelCase
- **Contexts**: `NomeContext.tsx`, `NomeProvider`, hook de acesso `useNome()`
- **Arquivos**: camelCase para utils/hooks, PascalCase para componentes
- **Pastas**: agrupar por domínio (GamePanel/, MechanicsPanel/, ClassSelector/)
- **CSS**: Tailwind utility classes, sem CSS modules ou styled-components
- **Reducer actions**: `SCREAMING_SNAKE_CASE`
- **Estado**: React Context + useReducer (sem Redux/Zustand)
- **i18n**: `t('chave', 'fallback')` do `src/i18n/`

### Backend
- **Módulos**: snake_case
- **Funções**: snake_case, privadas com prefixo `_`
- **Classes (Pydantic)**: PascalCase
- **Constantes**: UPPER_SNAKE_CASE
- **Logging**: `logging.getLogger('neon_scratch.modulo')`
- **Config**: env vars com defaults em `config.py`
- **Rotas**: FastAPI com routers em `main.py`
- **Endpoints**:
  - `POST /action` — ação do jogador
  - `GET /health` — health check
  - `POST /demo/inject-failure` — injetar falha (teste)
  - `POST /demo/clear-failure` — limpar falha
  - `GET /demo/logs` — logs da campanha
  - `GET /action/status` — status do turno

## Fluxo de uma Ação (POST /action)

1. **RetrieveLore** → `lore_retriever.retrieve_lore()`: busca em JSONs locais por keyword overlap
2. **InvokeDungeonMaster** → `dungeon_master.handler()`: modo single_shot (default) ou agentic
   - single_shot: Python executa tools, LLM só narra
   - agentic: LLM decide tools em loop (max 12 iterações)
3. **PersistCampaign** → SQLite via `campaign_manager.save_campaign()`
4. **FormatResponse** → inline em `main.py` (sem Lambda)

## UI Mechanics Panel

O painel "AWS Mechanics" do frontend exibe uma simulação visual do pipeline de processamento. Os passos do workflow e seus serviços reais:

| Passo               | Serviço    | Descrição                          |
|----------------------|------------|-------------------------------------|
| RetrieveLore         | App        | Leitura de JSONs + keyword scoring |
| InvokeDungeonMaster  | Ollama     | LLM local (mistral:7b)             |
| PersistCampaign      | SQLite     | Persistência em SQLite             |
| FormatResponse       | App        | Montagem inline da resposta        |

## Classes de Personagem (4)

| Classe           | HP  | Stat Principal     | Habilidade Especial                    |
|------------------|-----|--------------------|----------------------------------------|
| TabbyWarrior     | 120 | pawStrength (8)    | Nine Lives: sobrevive morte 1x         |
| SiameseMage      | 70  | arcane (9)         | Laser Focus: -10HP, 3x dano arcano    |
| MaineCoonPaladin | 100 | pawStrength (6)    | Holy Hairball Shield: block 15 dmg     |
| SphinxRogue      | 80  | agility/stealth (9)| Sandstorm Vanish: invisível 1 turno    |

## Localizações (6 Zonas)

NeonScratchLounge, ChromeAlley, RoombaCoreTower, NightMarket, SewersOfForgetfulness, IndustrialZone.

## Inimigos

RoombaDrone (30HP), LaserGangMember (40HP), MutantRat (50HP), EliteRoombaDrone (80HP), VacuumDemon (200HP, boss), CEORoomba (300HP, boss final).

## Modos de Jogo (DM_MODE)

- `single_shot` (default) — rápido, funciona com modelos pequenos (CPU)
- `agentic` — LLM decide ferramentas, requer modelo 7B+

## Ferramentas do Jogo (8)

roll-dice, apply-damage, update-inventory, award-xp, update-location, apply-effect, use-special-ability, update-quest-log

## Testes

Projeto **não possui testes automatizados**. Não adicionar sem orientação explícita.

## Lint/Format

Projeto **não possui linter ou formatador configurado**. O `tsconfig.json` tem `strict: true`, `noUnusedLocals`, `noUnusedParameters`. O `npm run build` executa o type-check do TypeScript via Vite.

## Git

- `pull.rebase=true`
- Commits em português
- Branches: `main` (Neon Scratch Lounge), `feature/heranca-de-cthulhu` (zumbis universitários)
