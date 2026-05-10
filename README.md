# Sniper Bot - Railway + Telegram + TradingView Webhook

## Start command no Railway

```bash
python start.py
```

Não configure `PORT` manualmente no Railway. O Railway injeta `PORT` automaticamente.

## Variáveis obrigatórias para Telegram

```env
BOT_TELEGRAM=true
TELEGRAM_BOT_TOKEN=seu_token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id
TELEGRAM_PARSE_MODE=HTML
```

## Horário correto no Telegram

Para mostrar o horário em Brasília/São Paulo:

```env
BOT_TIMEZONE=America/Sao_Paulo
BOT_TIME_FORMAT=%d/%m/%Y %H:%M:%S
```

O TradingView envia `time` como timestamp Unix em milissegundos. O bot converte esse valor para o fuso configurado em `BOT_TIMEZONE`.

## Confirmação de WIN/LOSS

Esta versão acompanha os sinais abertos e envia confirmação no Telegram quando um candle posterior toca o Take Profit ou o Stop Loss.

```env
WIN_LOSS_ALERTS=true
SAME_CANDLE_POLICY=conservative
MAX_OPEN_SIGNALS=50
```

Políticas para quando TP e SL são tocados no mesmo candle:

- `conservative`: marca LOSS, porque sem dados intrabar não dá para saber qual preço veio primeiro.
- `optimistic`: marca WIN.
- `skip`: marca INDEFINIDO.

## Endpoints

- `GET /health`: verifica se o bot está online.
- `POST /telegram/test`: envia uma mensagem de teste para o Telegram.
- `POST /webhook/tradingview`: recebe 1 candle por webhook, guarda o histórico, envia sinal e confirma WIN/LOSS.
- `POST /signal`: recebe uma lista de candles e envia o sinal para Telegram.
- `GET /candles/status`: mostra candles armazenados, sinais abertos e sinais fechados.

## Webhook do TradingView

Use a URL:

```text
https://SEU-APP.up.railway.app/webhook/tradingview
```

## TradingView: script recomendado

Use o arquivo `tradingview_sniper_bot.pine`. Ele envia o campo `time` como texto para evitar erro 422 no FastAPI/Pydantic.

Depois de alterar o Pine Script, salve, adicione ao gráfico e recrie o alerta do TradingView usando:

- Condição: `Sniper Bot - Enviar Candles`
- Opção: `Any alert() function call` / `Qualquer chamada de função...`
- Webhook URL: `https://SEU-APP.up.railway.app/webhook/tradingview`
