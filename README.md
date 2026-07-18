# 🚀 Pump.fun Telegram Trading Bot

A comprehensive Solana trading ecosystem with Telegram bot, WebSocket real-time data, and big wallet tracking.

## Features

### Telegram Bot
- 📊 **Portfolio Tracking** - Monitor positions with real-time PnL
- 💰 **Buy/Sell** - Execute trades via Telegram commands
- 🎯 **Limit Orders** - Set buy orders at target prices
- ⚙️ **Auto TP/SL** - Automatic take profit and stop loss
- 📈 **Dynamic SL** - Trailing stop loss that locks in profits
- 📜 **Trade History** - Track all trades with realized PnL
- 🐋 **Whale Tracking** - View big wallet holders on any token
- 🧠 **Smart Money Analysis** - Analyze buying/selling patterns

### Backend API
- 🔗 **REST API** - Token info, whale data, transaction history
- ⚡ **WebSocket** - Real-time price updates for frontend
- 📊 **Solana WebSocket** - Direct Solana chain subscriptions

## Project Structure

```
meteora-telegram-bot-pro13/
├── pumpfun_telegram_bot.py  # Main Telegram bot
├── pumpfun_bot.py           # Core trading logic
├── requirements.txt         # Bot dependencies
├── .env                     # Configuration (gitignored)
├── backend/                 # Python API for web
│   ├── api_server.py        # FastAPI server
│   ├── solana_websocket.py  # WebSocket & whale tracker
│   └── requirements.txt     # Backend dependencies
└── web/                     # Vue.js frontend (by agent habib)
    └── README.md            # API contract documentation
```

## Quick Start

### 1. Setup Bot
```bash
git clone https://github.com/gethoopp/meteoratoken-bot.git
cd meteoratoken-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
./venv/bin/python pumpfun_telegram_bot.py
```

### 2. Setup Backend API
```bash
cd backend
pip install -r requirements.txt
uvicorn api_server:app --reload --port 8000
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Show all commands |
| `/positions` | View portfolio with PnL |
| `/price <symbol>` | Get detailed price info |
| `/buy <mint> <sol>` | Buy token |
| `/sell <symbol> <percent>` | Sell token |
| `/settp [symbol] <percent>` | Set take profit |
| `/setsl [symbol] <percent>` | Set stop loss |
| `/dynamicsl [on/off]` | Toggle dynamic/trailing SL |
| `/whales <mint>` | View big wallet holders |
| `/smartmoney <mint>` | Analyze smart money activity |
| `/history [days]` | View trade history |
| `/pnl [today/week/month]` | View realized PnL |

## Dynamic Stop Loss

The bot features a dynamic SL that automatically adjusts as price rises:

- **Entry:** $0.001, **SL:** 50%
- **Price rises to:** $0.002 (100% gain)
- **Normal SL** triggers at: $0.0005 (-50% from entry)
- **Dynamic SL** triggers at: ~$0.00175 (-12.5% from high)

This locks in approximately half of your gains while still protecting downside.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/token/{mint}` | Token info with price |
| `GET /api/token/{mint}/holders` | Big wallet holders |
| `GET /api/token/{mint}/transactions` | Recent transactions |
| `WS /ws/token/{mint}` | Real-time price stream |

## Configuration

Create `.env` file:

```env
WALLET_ADDRESS=your_solana_wallet
PUMP_PRIVATE_KEY=your_private_key
HELIUS_API_KEY=your_helius_api_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
AUTO_TRADE=true
```

## Disclaimer

⚠️ **Use at your own risk.** This bot interacts with real money. Always test with small amounts first.

## License

MIT
