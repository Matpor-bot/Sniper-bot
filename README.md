# Portfolio ORB Multi v12.1 — XAUUSD + NAS100 + GER40

Esta versão junta os três robôs validados em um único deploy Railway:

- **Gold v10.3** — XAUUSD ORB com risco padrão 3%.
- **NAS100 v11** — NY Tech Breakout com risco padrão 2%.
- **GER40/DAX v12** — Europe Open Breakout com risco padrão 3%.

## Como usar

1. Suba esta pasta no Railway.
2. Copie as variáveis de `.env.example` para o Railway.
3. No TradingView, abra 3 gráficos M5:
   - XAUUSD/GOLD
   - NAS100/US100/USATECH
   - GER40/DE40/DAX
4. Cole o Pine `tradingview_portfolio_orb_multi.pine` em cada gráfico.
5. Crie 1 alerta por gráfico usando:
   - Condition: `Portfolio ORB Multi v12.1 - Webhook`
   - Opção: `Any alert() function call`
   - Frequency: `Once Per Bar Close`
   - Webhook URL: `https://SEU-RAILWAY.up.railway.app/webhook/tradingview`

## Risco padrão recomendado

```env
XAU_RISK_PER_TRADE_PCT=3.0
NAS_RISK_PER_TRADE_PCT=2.0
GER_RISK_PER_TRADE_PCT=3.0
MAX_TOTAL_OPEN_SIGNALS=3
MAX_OPEN_SIGNALS_PER_MARKET=1
```

No backtest combinado anterior, esta carteira foi a mais equilibrada entre retorno e drawdown:

- Gold 3% + NAS100 2% + GER40 3%.
- Capital simulado: US$500.
- Resultado histórico 2023-2025: cerca de US$6.051 final.
- Média mensal: cerca de 7,17%.
- DD máximo: cerca de 30,26%.

Esses números vêm dos relatórios CSV incluídos e não garantem resultado futuro.

## Importante

- Rode em demo antes.
- Confirme spread real da corretora nos horários dos setups.
- Se usar Pepperstone ou outra corretora CFD, confira tamanho de contrato, valor por ponto e margem de cada ativo.
- O cálculo de lote é estimado; ajuste `*_PIP_VALUE_PER_LOT_USD` se sua corretora usar contrato diferente.
