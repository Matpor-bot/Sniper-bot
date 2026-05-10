# Railway Forex Pro Scalper v8.2 Prime DD-Controlled

Bot de sinais para Forex/XAUUSD com webhook do TradingView, Telegram, dashboard e backtest offline. Esta versão é uma evolução da v8.1 com foco em **reduzir drawdown mantendo frequência de scalping**.

## O que mudou na v8.2

A v8.1 era ativa, mas no teste com risco de 2% teve drawdown alto. A v8.2 mantém o motor técnico da v8.1 e adiciona um filtro de edge por **ativo + hora UTC + dia da semana**, além de limite global de sinais abertos.

Motor técnico:

- EMA 9/21/75
- RSI 14
- MACD 12/26/9
- ADX/DI
- ATR
- Choppiness Index
- Pullback, breakout e sweep de liquidez
- Confirmação multi-timeframe
- Bloqueio de spike/lateralização
- Expiração rápida de sinal
- Limite por mercado e limite global de sinais abertos

Filtro v8.2:

| Ativo | Horas UTC permitidas | Dias permitidos |
|---|---|---|
| EURUSD | 06, 07, 10, 12, 13, 15 | segunda, terça, quinta |
| GBPUSD | 09, 10, 11, 12 | quinta, sexta |
| XAUUSD | 08, 10, 12, 13, 16 | segunda, terça, quarta, sexta |

Dias no Railway: `0=segunda, 1=terça, 2=quarta, 3=quinta, 4=sexta`.

## Resultado do backtest v8.2 — 2025

Dados usados: EURUSD, GBPUSD e XAUUSD M1 de 2025 convertidos para M5. Capital inicial: US$ 1.000. Risco: 2% por trade. Resultado sem spread/slippage porque os CSVs não tinham bid/ask.

| Métrica | v8.1 risco 2% | v8.2 risco 2% |
|---|---:|---:|
| Trades | 1.377 | 387 |
| Win rate | 54,03% | 63,57% |
| Profit Factor | 1,089 | 1,630 |
| Saldo final | US$ 2.157,07 | US$ 4.679,08 |
| Retorno total | +115,71% | +367,91% |
| Média mensal composta | +6,62% | +13,72% |
| Drawdown máximo | 31,51% | 11,79% |

Treino vs validação:

| Período | Trades | Win rate | PF | R total |
|---|---:|---:|---:|---:|
| Jan-Ago | 241 | 66,80% | 1,871 | 63,35R |
| Set-Dez | 146 | 58,22% | 1,309 | 16,88R |
| Ano completo | 387 | 63,57% | 1,630 | 80,24R |

## Deploy no Railway

Start command:

```bash
python start.py
```

Healthcheck:

```text
/health
```

Endpoints úteis:

```text
/
/health
/api/status
/strategy/status
/stats
/signals/open
/signals/closed
/webhook/debug
/webhook/tradingview
```

## TradingView

Use o arquivo:

```text
tradingview_pro_scalper_v8_2.pine
```

No TradingView:

1. Abra o gráfico em **5 minutos**.
2. Cole o Pine v8.2.
3. Adicione ao gráfico.
4. Crie alerta com **Any alert() function call**.
5. Webhook:

```text
https://SEU-APP.up.railway.app/webhook/tradingview
```

## Variáveis principais do Railway

Obrigatórias para Telegram:

```env
BOT_TELEGRAM=true
TELEGRAM_BOT_TOKEN=seu_token
TELEGRAM_CHAT_ID=seu_chat_id
```

Configuração v8.2 testada:

```env
ACCOUNT_BALANCE=1000
RISK_PER_TRADE_PCT=2.0
SYMBOL_ALLOWLIST=EURUSD,GBPUSD,XAUUSD
RECOMMENDED_TIMEFRAME=M5
SESSION_FILTER_ENABLED=true
SESSION_WINDOWS_UTC=06:00-18:00
EDGE_SCHEDULE_FILTER_ENABLED=true
EDGE_ALLOWED_HOURS_UTC=EURUSD:6,7,10,12,13,15|GBPUSD:9,10,11,12|XAUUSD:8,10,12,13,16
EDGE_ALLOWED_WEEKDAYS_UTC=EURUSD:0,1,3|GBPUSD:3,4|XAUUSD:0,1,2,4
MAX_TOTAL_OPEN_SIGNALS=2
MAX_OPEN_SIGNALS_PER_MARKET=1
```

## Cuidado importante

O resultado da v8.2 é muito melhor no histórico 2025, mas ainda é um backtest de um único ano e **sem custos reais de spread/slippage**. Em scalping, custo de execução muda bastante o resultado. Antes de conta real, rode em demo e acompanhe `/stats`, `/signals/closed` e os sinais do Telegram.
