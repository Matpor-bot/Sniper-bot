# Scalping Signal Bot

Bot de sinais para scalping, pronto para Railway.

## O que faz
- Recebe candles em JSON via HTTP
- Gera sinal BUY / SELL / HOLD
- Calcula stop loss e take profit por ATR
- Filtra tendência, momentum, volatilidade e spread
- Salva o último sinal em JSON e CSV
- Envia sinais para Telegram
- Suporta deploy no Railway e execução local

## Endpoints
- `GET /health`
- `GET /latest`
- `POST /signal`
- `POST /signal/csv`
- `POST /run-once`

## Exemplo de payload
```json
{
  "symbol": "EURUSD",
  "timeframe": "M1",
  "candles": [
    {
      "time": "2026-05-09T12:00:00Z",
      "open": 1.2345,
      "high": 1.2350,
      "low": 1.2338,
      "close": 1.2349,
      "volume": 1234
    }
  ]
}
```

## Railway
Start command:
```bash
uvicorn scalping_bot.app:app --host 0.0.0.0 --port $PORT
```

## Telegram
Defina:
- `BOT_TELEGRAM=true`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Observação
O Railway não acessa seu MetaTrader 5 local. Para operar em tempo real, envie as candles de uma fonte externa para o endpoint `/signal`.
