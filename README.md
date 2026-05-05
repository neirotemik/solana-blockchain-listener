# Solana Pump.fun Listener

Async Python listener for Solana WebSocket logs related to the pump.fun program.

## Features

- Solana `logsSubscribe` WebSocket listener
- Heuristic event parser
- Token creation detection
- Buy/sell trade detection
- Liquidity and migration event detection
- LRU deduplication
- Structured JSON output
- Reconnect logic

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` if needed.

## Run

```bash
python -m runner
```

## Tests

```bash
pytest
```

## License

MIT
