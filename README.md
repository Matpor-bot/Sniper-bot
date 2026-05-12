# Railway Gold ORB Scalper v10.1 — Pro Live Dashboard

Versão validada para **XAUUSD M5**, agora com dashboard profissional em tempo real usando histórico **Dukascopy M1 BID 2023-2025 convertido para M5**.

## Estratégia selecionada

**Gold ORB Scalper v10 — Opening Range Breakout**

- Ativo: `XAUUSD`
- Timeframe: `M5`
- Faixa de abertura: `13:30-13:45 UTC`
- Entrada: `BUY STOP` no topo da OR + `0.05 × range`
- Stop: `0.75 × range`
- Alvo: `2R`
- Expiração da entrada pendente: `120 minutos`
- Custo estimado no backtest: `0.35 ponto` round-turn
- Uma operação por dia

O bot envia uma **ordem pendente BUY STOP** no fechamento da faixa de abertura. Não é para entrar a mercado antes do rompimento.

## Resultado principal do backtest

Risco de 3% por trade:

| Período | Trades | Win rate | PF | Retorno | DD máx. |
|---|---:|---:|---:|---:|---:|
| Treino 2023-2024 | 323 | 41.80% | 1.25 | +197.26% | 37.03% |
| Validação 2025 | 170 | 45.88% | 1.52 | +253.89% | 25.13% |
| Total 2023-2025 | 493 | 43.20% | 1.34 | +951.98% | 37.03% |

Risco recomendado para demo: `3.0%`.
Risco extremo: `5.0%`, com drawdown histórico acima de 56%.


## Dashboard profissional em tempo real

A página inicial `/` agora mostra um painel visual completo:

- preço e último candle recebido do XAUUSD;
- fase atual do robô: aguardando faixa, formando ORB, janela aberta, ordem pendente ou trade ativo;
- high/low/range da abertura de 13:30-13:45 UTC;
- entrada BUY STOP estimada, SL, TP e lote quando houver ordem;
- gráfico interno com os candles recebidos pelo webhook;
- gráfico TradingView integrado como referência visual;
- últimos webhooks, sinais, resultados e estatísticas ao vivo;
- endpoints JSON: `/api/live`, `/api/candles/XAUUSD/M5`, `/api/backtest-summary`.

Importante: o painel interno só fica realmente em tempo real quando o alerta do TradingView está ativo enviando candles M5 para `/webhook/tradingview`. O gráfico TradingView é apenas referência visual externa; a lógica do bot usa os candles recebidos pelo webhook.

Variáveis opcionais do dashboard:

```env
DASHBOARD_REFRESH_MS=2000
TRADINGVIEW_DASHBOARD_SYMBOL=OANDA:XAUUSD
```

## Como usar no TradingView

1. Abra o gráfico de `XAUUSD` em **5 minutos**.
2. Cole o arquivo `tradingview_gold_orb_v10.pine` no Pine Editor.
3. Adicione ao gráfico.
4. Crie alerta com **Any alert() function call**.
5. Webhook URL: URL do seu Railway + `/webhook/tradingview`.
6. Frequência recomendada: **Once Per Bar Close**.

## Variáveis principais no Railway

Copie o `.env.example` e configure Telegram se quiser receber sinais.

Principais:

```env
STRATEGY_MODE=GOLD_ORB_V10
SYMBOL_ALLOWLIST=XAUUSD,GOLD
ORB_SYMBOL_ALLOWLIST=XAUUSD,GOLD
RISK_PER_TRADE_PCT=3.0
ORB_START_MINUTE_UTC=810
ORB_RANGE_MINUTES=15
ORB_TRADE_WINDOW_MINUTES=120
ORB_DIRECTION=BUY_STOP
ORB_BUFFER_MULT=0.05
ORB_STOP_RANGE_MULT=0.75
ORB_TAKE_R=2.0
MAX_TOTAL_OPEN_SIGNALS=1
MAX_OPEN_SIGNALS_PER_MARKET=1
```

## Aviso

Essa é uma estratégia agressiva de day trade. O backtest foi positivo, mas não garante resultado futuro. Rode primeiro em demo e valide spread, execução e slippage da corretora.
