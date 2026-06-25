# A Herança de Cthulhu — Roadmap de Adaptação Digital

## Visão Geral

Adaptar o loop de jogo do RPG **A Herança de Cthulhu** (101 Games, sistema SOLO10) para uma experiência digital com LLM narrativo local (Ollama), similar ao que fizemos com o Neon Scratch Lounge.

---

## Arquitetura Proposta

```
jogador → escolhe setor + ação
              ↓
        backend (FastAPI)
              ↓
    ┌─────┼──────────┐
    │     │          │
  sortear   executar   gerar
  evento    teste     narrativa
  do setor  SOLO10    (Ollama)
    │     │          │
    └─────┼──────────┘
          ↓
    atualizar estado
    (SQLite)
          ↓
    jogador vê:
    - narrativa do evento
    - resultado dos testes
    - estado (Saúde, Fome, Loucura, etc.)
    - ciclo dia/noite
```

---

## Status Atual (branch `feature/heranca-de-cthulhu`)

### ✅ Dados Criados (conteúdo original)

| Arquivo | Descrição |
|---------|-----------|
| `data/sectors.json` | 5 setores com conexões (Cidade Nova, Cidade Velha, Centro Industrial, Porto, Ermos) |
| `data/events/cidade_nova.json` | 20 eventos — ficção corporativa, tecnologia corrompida, néon fantasma |
| `data/events/cidade_velha.json` | 20 eventos — história, cultos, universidade, segredos antigos |
| `data/events/centro_industrial.json` | 20 eventos — toxinas, máquinas vivas, ferros-velho, horrores fabris |
| `data/events/porto.json` | 20 eventos — navios fantasma, profunda, contêineres, maré negra |
| `data/events/ermos.json` | 20 eventos — geometria errada, círculos de pedra, fazendas fantasmas |
| `data/adversaries.json` | 11 tipos: Insano, Cultista, Sacerdote Sombrio, Desmorto, Carniçal, Insano Híbrido, Abissal, Dagon, Fantasma, Fantasma Ancestral, Sobrevivente Hostil |
| `data/items.json` | 19 armas, 7 armaduras, 12 recursos |
| `data/npcs.json` | 10 tipos + 5 características + 5 NPCs notáveis |
| `data/refuges.json` | 5 tipos de refúgio + 7 upgrades |

### ❌ Pendente (Fase 2 em diante)

- [ ] Motor SOLO10: testes, combate, perigo, bônus de poder
- [ ] Modelos Pydantic (Sobrevivente, Refúgio, Estado de Jogo)
- [ ] Banco SQLite (persistência de campanha)
- [ ] Loop dia/noite com fases
- [ ] Locomoção entre setores
- [ ] Sistema de eventos (sortear + narrar)
- [ ] Sistema de encontros (neutro e violento)
- [ ] Ataque de Horda noturno
- [ ] Fome, Loucura e Postura
- [ ] Evolução (XP)
- [ ] Integração com Ollama para narrativa
- [ ] Frontend React

---

## Estrutura de Diretórios

```
backend/heranca/
├── __init__.py
├── main.py              # FastAPI routes
├── config.py            # Config (Ollama, paths)
├── models.py            # Pydantic models
├── database.py          # SQLite
├── game_engine.py       # SOLO10 rules
├── event_tables.py      # Load and roll events
├── oracle.py            # Oracle system
├── narrative.py         # LLM narrative
└── data/                # JSON data
    ├── sectors.json     # ✓ Criado
    ├── events/          # ✓ 5 arquivos (100 eventos)
    ├── adversaries.json # ✓ Criado
    ├── items.json       # ✓ Criado
    ├── npcs.json        # ✓ Criado
    └── refuges.json     # ✓ Criado
```

---

## Licenças

- **SOLO10**: Creative Commons CC BY (regras do sistema)
- **Conteúdo original (eventos, NPCs, itens)**: Criado por nós, livre para uso
- **Marcas e cenário "A Herança de Cthulhu"**: Propriedade da 101 Games
