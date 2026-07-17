# Pump.fun Auto TP/SL Bot

Bot otomatis untuk close position di [pump.fun](https://pump.fun) berdasarkan Take Profit dan Stop Loss.

## ✨ Features

- 📊 **Auto Monitor** - Monitor semua pump.fun token di wallet
- 🎯 **Multi-Level TP** - Set multiple take profit levels (5%, 10%, 15%, dll)
- 🛑 **Stop Loss** - Auto close jika loss melebihi threshold
- 📱 **Telegram Notifications** - Notifikasi realtime ke Telegram
- 🔒 **Dry Run Mode** - Mode monitoring tanpa trading

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Copy config template
cp .env.pumpfun.example .env.pumpfun

# Edit configuration
nano .env.pumpfun
```

### 2. Configure Settings

Edit `.env.pumpfun`:

```env
# Wallet address (required)
PUMP_WALLET_ADDRESS=YourWalletAddressHere111111111111111111111111

# Private key untuk trading (optional - kosongkan untuk DRY RUN)
PUMP_PRIVATE_KEY=

# Take Profit levels (comma separated)
TP_LEVELS=5,10,15,20,25

# Stop Loss percentage
SL_LEVEL=10

# Check interval (seconds)
CHECK_INTERVAL=30

# Telegram (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Helius RPC (recommended)
HELIUS_API_KEY=your_api_key
```

### 3. Run Bot

```bash
# Activate virtual environment
source venv/bin/activate

# Check positions first
python pumpfun_cli.py check

# Run bot
python pumpfun_cli.py run
```

## 📖 Usage

### CLI Commands

```bash
# Check current positions
python pumpfun_cli.py check

# Run with default settings (from .env)
python pumpfun_cli.py run

# Run with custom TP/SL
python pumpfun_cli.py run --tp 5,10,20,30 --sl 15

# Run with specific wallet
python pumpfun_cli.py run --wallet <WALLET_ADDRESS>

# Add manual position tracking
python pumpfun_cli.py run --positions "MINT:0.000001:1000:SYMBOL"
```

### Direct Python Usage

```python
from pumpfun_bot import PumpFunBot
import asyncio

bot = PumpFunBot(
    wallet_address="YOUR_WALLET",
    take_profit_levels=[5, 10, 15, 20, 25],
    stop_loss_percent=10,
    check_interval=30,
)

# Add manual position with known entry price
bot.add_manual_position(
    mint="TOKEN_MINT_ADDRESS",
    entry_price=0.000001,  # SOL
    amount=1000000,
    symbol="TOKEN"
)

asyncio.run(bot.start())
```

## 🎯 How TP/SL Works

### Take Profit
- Bot tracks entry price saat pertama kali detect position
- Saat price naik mencapai TP level, bot sell sebagian position
- Contoh dengan 5 TP levels (5%, 10%, 15%, 20%, 25%):
  - Saat +5%: sell 20% position
  - Saat +10%: sell 20% lagi
  - dst...

### Stop Loss
- Jika loss melebihi SL threshold, bot close seluruh position
- Example: SL 10% = close jika loss > 10%

## ⚠️ Important Notes

### DRY RUN Mode
- Jika `PUMP_PRIVATE_KEY` kosong, bot hanya monitor tanpa trading
- Gunakan mode ini untuk testing dulu

### RPC Rate Limits
- Public RPC punya rate limit
- Recommended: Gunakan Helius (gratis) untuk better performance
- Sign up: https://helius.dev

### Position Tracking
- Bot detect position baru saat pertama kali monitor
- Entry price = current price saat first detection
- Untuk tracking dengan entry price spesifik, gunakan `add_manual_position()`

## 📱 Telegram Setup

1. Buat bot via [@BotFather](https://t.me/BotFather)
2. Copy token ke `TELEGRAM_BOT_TOKEN`
3. Message bot anda
4. Get chat ID dari: `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Copy chat ID ke `TELEGRAM_CHAT_ID`

## 🔧 Files

```
├── pumpfun_bot.py          # Main bot logic
├── pumpfun_cli.py          # CLI interface
├── .env.pumpfun.example    # Config template
└── README_PUMPFUN.md       # This file
```

## 🛡️ Security

- NEVER share private key
- Gunakan dedicated wallet untuk trading
- Test dengan DRY RUN mode dulu
- Start dengan small position

## 📝 License

MIT License - Use at your own risk.

---

Made for pump.fun trading automation 🚀
