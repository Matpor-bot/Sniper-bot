# Railway Deploy

## Start command correto

Use este comando no Railway/Render/etc.:

```bash
python start.py
```

Nao use `--port '$PORT'` no painel. O arquivo `start.py` ja le a porta pela variavel de ambiente `PORT`.

## Alternativa com uvicorn via shell

```bash
sh -c 'uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}'
```

## Endpoints

- `/` retorna status online
- `/health` retorna status ok
- `/signal` gera sinal simples com base nos candles enviados
