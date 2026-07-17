# 🚀 Pump.fun Telegram Trading Bot

A Telegram bot for trading tokens on [Pump.fun](https://pump.fun) with automatic Take Profit (TP) and Stop Loss (SL) features.

## Features

- 📊 **Portfolio Tracking** - Monitor positions with real-time PnL
- 💰 **Buy/Sell** - Execute trades via Telegram commands
- 🎯 **Limit Orders** - Set buy orders at target prices
- ⚙️ **Auto TP/SL** - Automatic take profit and stop loss (global or per-token)
- 📜 **Trade History** - Track all trades with realized PnL
- 🔄 **Multi-Pool Support** - Works with bonding curve and graduated (Raydium) tokens

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show all commands |
| `/positions` | View portfolio with PnL |
| `/price <symbol>` | Get detailed price info |
| `/buy <mint> <sol>` | Buy token |
| `/sell <symbol> <percent>` | Sell token |
| `/limitbuy <mint> <price> <sol>` | Set limit buy order |
| `/limits` | View pending limit orders |
| `/settp [symbol] <percent>` | Set take profit |
| `/setsl [symbol] <percent>` | Set stop loss |
| `/history [days]` | View trade history |
| `/pnl [today/week/month]` | View realized PnL |

## Setup

### 1. Clone Repository
```bash
git clone https://github.com/gethoopp/meteoratoken-bot.git
cd meteoratoken-bot
```

### 2. Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 5. Run Bot
```bash
./venv/bin/python pumpfun_telegram_bot.py
```

## Configuration

Create a `.env` file with:

```env
WALLET_ADDRESS=your_solana_wallet
PUMP_PRIVATE_KEY=your_private_key
HELIUS_API_KEY=your_helius_api_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Getting API Keys

1. **Helius API**: Free at [helius.xyz](https://helius.xyz)
2. **Telegram Bot**: Create via [@BotFather](https://t.me/BotFather)
3. **Chat ID**: Send `/start` to [@userinfobot](https://t.me/userinfobot)

## Examples

```
# Buy 0.05 SOL worth of a token
/buy DiaXHsNJwvGXEjx1HN7phGL7YfHPtBuvzHoCk28Apump 0.05

# Set 50% take profit for all tokens
/settp 50

# Set 30% stop loss for specific token
/setsl DBULL 30

# Create limit buy order
/limitbuy DBULL 0.00003 0.05

# Check realized PnL this month
/pnl month
```

## Disclaimer

⚠️ **Use at your own risk.** This bot interacts with real money. Always test with small amounts first.

## License

MIT
