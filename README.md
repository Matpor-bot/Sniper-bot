# Sniper Bot v6 - Pro Scalper + Railway + Telegram + TradingView

Esta versao nao opera mais apenas pelo candle anterior. Ela usa uma estrategia de score por confluencia:

- EMA 9/21/50 para tendencia e direcao
- VWAP para vies intraday
- RSI para momentum sem sobrecompra/sobrevenda extrema
- MACD para confirmacao de momentum
- ADX / +DI / -DI para forca e direcao da tendencia
- ATR para volatilidade e calculo dinamico de Stop/Take
- Bollinger Bands para evitar entradas muito esticadas
- Volume medio para filtrar candles fracos
- Rompimento/pullback em candle fechado

## Start command no Railway

```bash
python start.py
```

Nao configure `PORT` manualmente no Railway. O Railway injeta `PORT` automaticamente.

## Variaveis obrigatorias para Telegram

```env
BOT_TELEGRAM=true
TELEGRAM_BOT_TOKEN=seu_token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id
TELEGRAM_PARSE_MODE=HTML
```

## Variaveis recomendadas da estrategia

```env
SCORE_THRESHOLD=7
SCORE_DIFF_MIN=2
EMA_FAST=9
EMA_SLOW=21
EMA_TREND=50
RSI_PERIOD=14
MACD_FAST=12
MACD_SLOW=26
MACD_SIGNAL=9
ATR_PERIOD=14
ADX_PERIOD=14
MIN_ADX=18
BB_PERIOD=20
BB_STD=2.0
VWAP_PERIOD=50
VOLUME_PERIOD=20
BREAKOUT_LOOKBACK=5
MIN_ATR_PCT=0.00025
MAX_ATR_PCT=0.025
MIN_VOLUME_MULT=1.05
MIN_BODY_RATIO=0.35
ATR_STOP_MULT=1.2
ATR_TAKE_MULT=1.6
ALLOW_MULTIPLE_OPEN_SIGNALS=false
```

Se voce tinha `SCORE_THRESHOLD=4` da versao antiga, altere para `7` ou `8`. Quanto maior, menos sinais e mais filtro.

## Horario correto no Telegram

```env
BOT_TIMEZONE=America/Sao_Paulo
BOT_TIME_FORMAT=%d/%m/%Y %H:%M:%S
```

## Confirmacao de WIN/LOSS

Esta versao acompanha os sinais abertos e envia confirmacao no Telegram quando um candle posterior toca o Take Profit ou o Stop Loss.

```env
WIN_LOSS_ALERTS=true
SAME_CANDLE_POLICY=conservative
MAX_OPEN_SIGNALS=50
```

Politicas para quando TP e SL sao tocados no mesmo candle:

- `conservative`: marca LOSS, porque sem dados intrabar nao da para saber qual preco veio primeiro.
- `optimistic`: marca WIN.
- `skip`: marca INDEFINIDO.

## Endpoints

- `GET /health`: verifica se o bot esta online.
- `GET /strategy/status`: mostra a configuracao atual da estrategia.
- `POST /telegram/test`: envia uma mensagem de teste para o Telegram.
- `POST /webhook/tradingview`: recebe 1 candle por webhook, guarda o historico, envia sinal e confirma WIN/LOSS.
- `POST /signal`: recebe uma lista de candles e envia o sinal para Telegram.
- `GET /candles/status`: mostra candles armazenados, sinais abertos e sinais fechados.

## Webhook do TradingView

Use a URL:

```text
https://SEU-APP.up.railway.app/webhook/tradingview
```

## TradingView: script recomendado

Use o arquivo `tradingview_sniper_bot.pine`.

Depois de alterar o Pine Script, salve, adicione ao grafico e recrie o alerta do TradingView usando:

- Condicao: `Sniper Bot - Enviar Candles`
- Opcao: `Any alert() function call` / `Qualquer chamada de funcao...`
- Webhook URL: `https://SEU-APP.up.railway.app/webhook/tradingview`

## Observacao importante

Nenhuma estrategia garante lucro. Esta versao filtra melhor as entradas, mas ainda precisa ser testada em conta demo e validada por ativo/timeframe antes de usar dinheiro real.
