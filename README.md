# Sniper Bot - Railway + Telegram + TradingView Webhook

## Start command no Railway

```bash
python start.py
```

## Variáveis obrigatórias para Telegram

```env
BOT_TELEGRAM=true
TELEGRAM_BOT_TOKEN=seu_token_do_bot
TELEGRAM_CHAT_ID=seu_chat_id
TELEGRAM_PARSE_MODE=HTML
```

Não configure `PORT` manualmente no Railway. O Railway injeta `PORT` automaticamente.

## Endpoints

- `GET /health`: verifica se o bot está online.
- `POST /telegram/test`: envia uma mensagem de teste para o Telegram.
- `POST /webhook/tradingview`: recebe 1 candle por webhook, guarda o histórico e envia sinal para Telegram.
- `POST /signal`: recebe uma lista de candles e envia o sinal para Telegram.
- `GET /candles/status`: mostra quantos candles foram armazenados por símbolo/timeframe.

## Webhook do TradingView

Use a URL:

```text
https://SEU-APP.up.railway.app/webhook/tradingview
```

Mensagem do alerta:

```json
{
  "symbol": "{{ticker}}",
  "timeframe": "{{interval}}",
  "time": "{{time}}",
  "open": {{open}},
  "high": {{high}},
  "low": {{low}},
  "close": {{close}},
  "volume": {{volume}}
}
```

## TradingView: script recomendado

Use o arquivo `tradingview_sniper_bot.pine`. Ele envia o campo `time` como texto para evitar erro 422 no FastAPI/Pydantic.

Depois de alterar o Pine Script, salve, adicione ao gráfico e recrie o alerta do TradingView usando:

- Condição: `Sniper Bot - Enviar Candles`
- Opção: `Any alert() function call` / `Qualquer chamada de função...`
- Webhook URL: `https://SEU-APP.up.railway.app/webhook/tradingview`
