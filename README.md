# SindGreenMentor — Futebol Betting Brain

Robot de análise de apostas em futebol 11 com motor de decisão, scanner pré-jogo e ao vivo, stake por EV (1–10) e PWA instalável no telemóvel.

**Site online:** https://futebol-betting-brain.onrender.com  
**Repositório:** [github.com/pedromja/futebol-betting-brain](https://github.com/pedromja/futebol-betting-brain)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/pedromja/futebol-betting-brain)

## Funcionalidades

- **Pré-jogo** — descobre jogos nas próximas horas, rankeia por valor esperado (EV) e sugere stake
- **Ao vivo** — lista jogos in-play, odds em tempo real (API-Football → ESPN → pré-jogo) e filtros de tempo
- **PWA** — interface tipster com tabs Pré-jogo | Ao vivo | Histórico, dashboard green/red e ROI
- **Histórico** — grava tips em `data/predictions.jsonl` e resolve win/loss automaticamente
- **CLI** — análise manual, demos, scan, live-watch com alertas

## Início rápido (PC)

```powershell
cd C:\Users\pedro\futebol-betting-brain
pip install -r requirements.txt
copy .env.example .env
# Edita .env com as tuas chaves API
.\scripts\start_pwa.ps1
```

Abre no browser: `http://127.0.0.1:8765/`

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `API_FOOTBALL_KEY` | Recomendada | Jogos ao vivo e odds in-play (~100 req/dia grátis) |
| `OPENWEATHERMAP_API_KEY` | Opcional | Meteorologia nos jogos |
| `FOOTBALL_DATA_API_KEY` | Opcional | Fixtures e stats extra |
| `XAI_API_KEY` | Opcional | Notícias no X (DeepSearch) |

Copia `.env.example` para `.env` e preenche as chaves. O ficheiro `.env` **nunca** vai para o GitHub.

## Comandos CLI

```powershell
# Scanner pré-jogo (12h, banca 100€)
python main.py --scan --bankroll 100

# Listar jogos ao vivo
python main.py --live-list --live-league "World"

# Analisar jogos ao vivo
python main.py --live-scan --live-league "World" --bankroll 100

# Vigilância contínua com alertas
python main.py --live-watch --live-league "World"

# Resolver histórico win/loss
python main.py --resolve-predictions
```

## API web (PWA)

| Endpoint | Descrição |
|----------|-----------|
| `GET /` | Interface PWA |
| `GET /api/scan` | Scanner pré-jogo |
| `GET /api/live` | Análise ao vivo |
| `GET /api/live/list` | Lista jogos in-play |
| `GET /api/tips/history` | Histórico com performance |
| `POST /api/tips/resolve` | Resolver tips pendentes |
| `GET /health` | Health check (deploy) |

## Site na internet

A PWA está publicada em **https://futebol-betting-brain.onrender.com** (deploy automático a cada push no GitHub).

No telemóvel: abre o link → **Adicionar ao ecrã principal**.

### Chaves API na nuvem

O tab **Ao vivo** precisa de `API_FOOTBALL_KEY` no painel Render:

1. [dashboard.render.com](https://dashboard.render.com) → serviço `futebol-betting-brain` → **Environment**
2. Adiciona `API_FOOTBALL_KEY` (copia do teu `.env` local)
3. **Save Changes** (o site reinicia)

Atalho no PC (com `RENDER_API_KEY` no `.env`):

```powershell
.\scripts\render_sync_env.ps1
```

### Domínio próprio (opcional)

Se tiveres um domínio (ex: `mentor.seudominio.pt`):

1. Render → `futebol-betting-brain` → **Settings** → **Custom Domains** → Add
2. No teu DNS, cria um CNAME para `futebol-betting-brain.onrender.com`

Guia completo: [`deploy/COMECE_AQUI.txt`](deploy/COMECE_AQUI.txt)

> **Nota:** Plano grátis adormece após 15 min sem visitas (1.º acesso ~30s). Histórico na nuvem é efémero — no PC fica em `data/predictions.jsonl`.

## Estrutura do projeto

```
bankroll/     stake EV 1–10 e gestão de banca
live/         filtros de tempo e lógica in-play
scanner/      scan pré-jogo e live ranker
history/      gravação e resolução de tips
web/          API FastAPI + PWA estática
scripts/      utilitários (push GitHub, PWA local, resolver tips)
```

## Testes

```powershell
python -m pytest tests/ -q
```

## Licença

Uso pessoal / projeto privado SindicatoGreen.