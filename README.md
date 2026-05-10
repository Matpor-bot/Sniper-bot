# Railway Forex Pro Scalper v7

Bot profissional de sinais de scalping Forex/XAUUSD via **TradingView webhook + FastAPI + Railway + Telegram**.

## O que foi melhorado nesta versão

- Filtro de sessão de liquidez: Londres e overlap Londres/NY por padrão.
- Filtro de spread quando `bid/ask` estiverem disponíveis.
- Filtro de volatilidade por ATR mínimo/máximo.
- Filtro anti-chop por Choppiness Index.
- Filtro anti-spike para evitar candle anormal.
- Confirmação multi-timeframe por agregação dos candles recebidos.
- Score técnico com EMA 9/21/50, VWAP, RSI, MACD, ADX/DI, Bollinger, volume, rompimento/pullback e sweep de liquidez.
- Cooldown entre sinais para reduzir overtrading.
- Bloqueio de múltiplos sinais abertos por ativo/timeframe.
- Confirmação automática de WIN/LOSS por candles posteriores.
- Dashboard visual no endpoint `/`.
- Estatísticas em `/stats`, `/api/status`, `/signals/open`, `/signals/closed`.
- Telegram mais profissional com score, filtros, MTF, zona de entrada, SL, TP, RR e gestão.
- Start command seguro para Railway usando `python start.py`.

## Deploy no Railway

1. Suba todos os arquivos deste ZIP no GitHub, na raiz do repositório.
2. Crie um projeto no Railway a partir do GitHub.
3. Em **Variables**, configure as variáveis do `.env.example`.
4. Use o start command:

```bash
python start.py
```

Não configure `PORT` manualmente. O Railway injeta a porta automaticamente.

## Variáveis obrigatórias do Telegram

```env
BOT_TELEGRAM=true
TELEGRAM_BOT_TOKEN=seu_token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id
TELEGRAM_PARSE_MODE=HTML
```

Teste o Telegram em:

```text
https://SEU-APP.up.railway.app/telegram/test
```

## TradingView

Use o arquivo:

```text
tradingview_pro_scalper_v7.pine
```

Depois:

1. Cole no Pine Editor.
2. Salve e adicione ao gráfico.
3. Crie um alerta com a condição `Any alert() function call`.
4. Webhook URL:

```text
https://SEU-APP.up.railway.app/webhook/tradingview
```

## Endpoints principais

- `/` — dashboard visual.
- `/health` — status simples para Railway.
- `/api/status` — status completo.
- `/webhook/tradingview` — recebe candles do TradingView.
- `/telegram/test` — testa Telegram.
- `/stats` — win/loss/win rate.
- `/signals/open` — sinais abertos.
- `/signals/closed` — resultados fechados.

## Sobre filtros de sessão

Por padrão:

```env
SESSION_WINDOWS_UTC=07:00-11:00,12:30-16:30
```

Isso prioriza horários de maior liquidez. Ajuste conforme seu ativo, corretora e horário de verão.

## Sobre notícias

O bot não consulta calendário econômico por conta própria. Para travar manualmente horários de notícia:

```env
NEWS_BLACKOUT_ENABLED=true
NEWS_BLACKOUT_WINDOWS_UTC=2026-05-10T12:25:00Z/2026-05-10T13:05:00Z;2026-05-12T18:55:00Z/2026-05-12T19:20:00Z
```

## Observação importante

Este bot é sinalizador. Ele não executa ordens. Nenhuma estratégia garante lucro. Valide em demo, ajuste por ativo/timeframe e considere spread, slippage e execução real antes de usar dinheiro real.
