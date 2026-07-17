#!/usr/bin/env python3
"""
Pump.fun Telegram Bot dengan Interactive TP/SL
User bisa set TP dan SL lewat Telegram commands.

Commands:
/start - Mulai bot
/status - Lihat posisi dan settings
/settp <percent> - Set take profit (misal: /settp 10)
/setsl <percent> - Set stop loss (misal: /setsl 5)
/cleartp - Hapus take profit
/clearsl - Hapus stop loss
/positions - Lihat semua posisi
/sell <mint> <percent> - Manual sell (misal: /sell ABC123 50)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

import aiohttp
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pumpfun_telegram.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


class PumpFunTelegramBot:
    """Bot dengan Telegram interactive commands untuk TP/SL"""

    PUMP_API_BASE = "https://frontend-api.pump.fun"
    PUMP_TRADE_API = "https://pumpportal.fun/api/trade-local"
    HELIUS_RPC = "https://mainnet.helius-rpc.com"
    TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"

    def __init__(self):
        # Wallet config
        self.private_key = os.getenv("PUMP_PRIVATE_KEY", "")
        self.helius_api_key = os.getenv("HELIUS_API_KEY", "")
        
        # Auto-derive wallet address from private key if available
        self.wallet_address = self._derive_wallet_address()
        
        # Telegram config
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        
        # TP/SL Settings - user controlled via Telegram
        self.take_profit: Optional[float] = None  # Single TP level
        self.stop_loss: Optional[float] = None    # Single SL level
        self.auto_trade = os.getenv("AUTO_TRADE", "false").lower() == "true"
        
        # Check interval
        self.check_interval = int(os.getenv("CHECK_INTERVAL", "30"))
        
        # Position tracking
        # {mint: {"entry_price": float, "amount": float, "symbol": str, "tp_executed": bool, "sl_executed": bool}}
        self.positions: dict = {}
        
        # Limit orders tracking
        # {order_id: {"mint": str, "symbol": str, "target_price": float, "sol_amount": float, "created_at": str}}
        self.limit_orders: dict = {}
        self.next_order_id = 1
        
        # Trade history for realized PnL tracking
        self.trade_history_file = os.path.join(os.path.dirname(__file__), "trade_history.json")
        self.trade_history: list = self._load_trade_history()
        
        # HTTP session
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Running flag
        self.running = False
        
        # Last update ID for Telegram polling
        self.last_update_id = 0
    
    def _derive_wallet_address(self) -> str:
        """Get wallet address - prioritize env variable"""
        # ALWAYS use env wallet if set (user specified)
        env_wallet = os.getenv("WALLET_ADDRESS", "")
        if env_wallet:
            logger.info(f"Using wallet from env: {env_wallet}")
            return env_wallet
        
        # Only derive from private key if no env wallet
        if not self.private_key:
            return ""
        
        try:
            from solders.keypair import Keypair
            
            # Check if private key is hex format (64 chars = 32 bytes)
            if len(self.private_key) == 64:
                seed_bytes = bytes.fromhex(self.private_key)
                keypair = Keypair.from_seed(seed_bytes)
                derived = str(keypair.pubkey())
                logger.info(f"Derived wallet from private key: {derived}")
                return derived
            else:
                keypair = Keypair.from_base58_string(self.private_key)
                derived = str(keypair.pubkey())
                logger.info(f"Derived wallet from private key: {derived}")
                return derived
                
        except Exception as e:
            logger.warning(f"Could not derive wallet from private key: {e}")
            return ""
        
        logger.info(f"Bot initialized for wallet: {self.wallet_address}")

    def _load_trade_history(self) -> list:
        """Load trade history from JSON file"""
        try:
            if os.path.exists(self.trade_history_file):
                with open(self.trade_history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load trade history: {e}")
        return []
    
    def _save_trade_history(self):
        """Save trade history to JSON file"""
        try:
            with open(self.trade_history_file, 'w') as f:
                json.dump(self.trade_history, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save trade history: {e}")
    
    def _record_trade(self, trade_type: str, symbol: str, mint: str, 
                      amount_tokens: float, amount_sol: float, price_usd: float,
                      invested_usd: float = 0, pnl_usd: float = 0, pnl_percent: float = 0):
        """Record a trade to history"""
        import datetime
        trade = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": trade_type,  # "buy" or "sell"
            "symbol": symbol,
            "mint": mint,
            "amount_tokens": amount_tokens,
            "amount_sol": amount_sol,
            "price_usd": price_usd,
            "invested_usd": invested_usd,
            "received_usd": amount_tokens * price_usd if trade_type == "sell" else 0,
            "pnl_usd": pnl_usd,
            "pnl_percent": pnl_percent,
        }
        self.trade_history.append(trade)
        self._save_trade_history()
        logger.info(f"Recorded {trade_type}: {symbol} PnL: ${pnl_usd:.2f}")

    async def start(self):
        """Start the bot"""
        self.running = True
        self.session = aiohttp.ClientSession()
        
        logger.info("🚀 Pump.fun Telegram Bot started!")
        
        await self.send_message(
            "🚀 *Pump.fun Bot Started!*\n\n"
            f"Wallet: `{self.wallet_address[:8]}...{self.wallet_address[-4:]}`\n\n"
            "*Commands:*\n"
            "/status - Lihat posisi & settings\n"
            "/settp <persen> - Set take profit\n"
            "/setsl <persen> - Set stop loss\n"
            "/cleartp - Hapus take profit\n"
            "/clearsl - Hapus stop loss\n"
            "/positions - Lihat semua posisi\n"
            "/sell <mint> <persen> - Manual sell"
        )
        
        try:
            # Run both tasks concurrently
            await asyncio.gather(
                self.telegram_polling_loop(),
                self.position_monitor_loop()
            )
        except asyncio.CancelledError:
            logger.info("Bot cancelled")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the bot"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("🛑 Bot stopped")

    async def telegram_polling_loop(self):
        """Poll Telegram for new messages/commands"""
        while self.running:
            try:
                await self.process_telegram_updates()
                await asyncio.sleep(1)  # Poll every second
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                await asyncio.sleep(5)

    async def position_monitor_loop(self):
        """Monitor positions and check TP/SL"""
        while self.running:
            try:
                await self.check_positions()
                await self.check_limit_orders()  # Check limit buy orders
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Position monitor error: {e}")
                await asyncio.sleep(10)

    async def process_telegram_updates(self):
        """Process incoming Telegram messages"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 10}
            
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    return
                
                data = await response.json()
                if not data.get("ok"):
                    return
                
                for update in data.get("result", []):
                    self.last_update_id = update["update_id"]
                    
                    message = update.get("message", {})
                    text = message.get("text", "")
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    
                    # Only respond to authorized chat
                    if chat_id != self.telegram_chat_id:
                        continue
                    
                    await self.handle_command(text)
                    
        except Exception as e:
            logger.error(f"Error processing Telegram updates: {e}")

    async def handle_command(self, text: str):
        """Handle Telegram commands"""
        if not text.startswith("/"):
            return
        
        parts = text.split()
        # Handle /command@botname format
        command = parts[0].lower().split("@")[0]
        args = parts[1:] if len(parts) > 1 else []
        
        logger.info(f"Processing command: {command} with args: {args}")
        
        if command == "/start":
            await self.cmd_start()
        elif command == "/status":
            await self.cmd_status()
        elif command == "/settp":
            await self.cmd_settp(args)
        elif command == "/setsl":
            await self.cmd_setsl(args)
        elif command == "/cleartp":
            await self.cmd_cleartp()
        elif command == "/clearsl":
            await self.cmd_clearsl()
        elif command == "/positions":
            await self.cmd_positions()
        elif command == "/sell":
            await self.cmd_sell(args)
        elif command == "/addtoken":
            await self.cmd_addtoken(args)
        elif command == "/setentry":
            await self.cmd_setentry(args)
        elif command == "/setinvested":
            await self.cmd_setinvested(args)
        elif command == "/refresh":
            await self.cmd_refresh()
        elif command == "/buy":
            await self.cmd_buy(args)
        elif command == "/limitbuy":
            await self.cmd_limitbuy(args)
        elif command == "/limits":
            await self.cmd_limits()
        elif command == "/cancellimit":
            await self.cmd_cancellimit(args)
        elif command == "/price":
            await self.cmd_price(args)
        elif command == "/history":
            await self.cmd_history(args)
        elif command == "/pnl":
            await self.cmd_pnl(args)
        elif command == "/help":
            await self.cmd_start()
        else:
            await self.send_message(f"❓ Unknown command: {command}\\nType /help for available commands")

    async def cmd_addtoken(self, args: list):
        """Manually add a token position"""
        if len(args) < 3:
            await self.send_message(
                "❌ Usage: /addtoken <mint> <amount> <entry_price>\n\n"
                "Example:\n"
                "`/addtoken ABC123...xyz 16670 0.0000001`\n\n"
                "• mint = token contract address\n"
                "• amount = jumlah token\n"
                "• entry_price = harga beli (SOL)"
            )
            return
        
        mint = args[0]
        try:
            amount = float(args[1])
            entry_price = float(args[2])
        except ValueError:
            await self.send_message("❌ Invalid number format")
            return
        
        # Get token symbol from pump.fun
        symbol = "UNKNOWN"
        token_info = await self.get_pump_token_info(mint)
        if token_info:
            symbol = token_info.get("symbol", "UNKNOWN")
        
        self.positions[mint] = {
            "entry_price": entry_price,
            "amount": amount,
            "symbol": symbol,
            "tp_executed": False,
            "sl_executed": False,
        }
        
        await self.send_message(
            f"✅ Token added manually!\n\n"
            f"Token: {symbol}\n"
            f"Amount: {amount:,.0f}\n"
            f"Entry: {entry_price:.10f} SOL\n"
            f"Mint: `{mint[:12]}...`"
        )

    async def cmd_start(self):
        """Handle /start command"""
        await self.send_message(
            "🚀 *Pump.fun Trading Bot*\n\n"
            "*📊 Portfolio:*\n"
            "• /positions - Lihat posisi + PnL\n"
            "• /status - Lihat settings\n"
            "• /price <symbol> - Detail harga\n"
            "• /refresh - Refresh data\n\n"
            "*💰 Trading:*\n"
            "• /buy <mint> <sol> - Beli token\n"
            "• /sell <symbol> <persen> - Jual token\n"
            "• /limitbuy <mint> <price> <sol> - Limit buy\n"
            "• /limits - Lihat limit orders\n\n"
            "*📜 History & PnL:*\n"
            "• /history [days] - Trade history\n"
            "• /pnl [today/week/month] - Realized PnL\n\n"
            "*⚙️ TP/SL Settings:*\n"
            "• /settp [symbol] <persen> - Set TP\n"
            "• /setsl [symbol] <persen> - Set SL\n"
            "• /setinvested <symbol> <usd> - Set invested"
        )

    async def cmd_status(self):
        """Handle /status command"""
        tp_str = f"{self.take_profit}%" if self.take_profit else "Not set"
        sl_str = f"{self.stop_loss}%" if self.stop_loss else "Not set"
        
        msg = (
            "📊 *Current Settings*\n\n"
            f"Take Profit: {tp_str}\n"
            f"Stop Loss: {sl_str}\n"
            f"Auto Trade: {'✅ ON' if self.auto_trade else '❌ OFF'}\n"
            f"Check Interval: {self.check_interval}s\n"
            f"Positions Tracked: {len(self.positions)}\n\n"
            f"Wallet: `{self.wallet_address[:8]}...`"
        )
        await self.send_message(msg)

    async def cmd_settp(self, args: list):
        """Handle /settp command - set take profit (global or per-token)"""
        if not args:
            await self.send_message(
                "❌ *Usage:*\n"
                "`/settp <percent>` → Set TP global\n"
                "`/settp <symbol> <percent>` → Set TP per token\n\n"
                "*Example:*\n"
                "`/settp 50` → Semua token auto sell +50%\n"
                "`/settp DBULL 30` → DBULL auto sell +30%\n"
                "`/settp Himgajria 100` → Himgajria auto sell +100%"
            )
            return
        
        try:
            # Check if first arg is a number (global) or symbol (per-token)
            if len(args) == 1:
                # Global TP
                tp = float(args[0])
                if tp <= 0:
                    await self.send_message("❌ TP harus lebih dari 0%")
                    return
                
                self.take_profit = tp
                self.auto_trade = True
                
                sl_str = f"-{self.stop_loss}%" if self.stop_loss else "Not set"
                await self.send_message(
                    f"✅ *Global Take Profit Set!*\n\n"
                    f"📈 TP: +{tp}% (semua token)\n"
                    f"📉 SL: {sl_str}\n"
                    f"🤖 Auto Trade: ON"
                )
            else:
                # Per-token TP
                symbol = args[0].upper()
                tp = float(args[1])
                if tp <= 0:
                    await self.send_message("❌ TP harus lebih dari 0%")
                    return
                
                # Find token by symbol
                found = False
                for mint, pos in self.positions.items():
                    if pos.get("symbol", "").upper() == symbol:
                        pos["tp"] = tp
                        pos["tp_executed"] = False
                        found = True
                        self.auto_trade = True
                        
                        sl_str = f"-{pos.get('sl', 'Not set')}%" if pos.get('sl') else "Global"
                        await self.send_message(
                            f"✅ *Take Profit Set for {pos['symbol']}!*\n\n"
                            f"📈 TP: +{tp}%\n"
                            f"📉 SL: {sl_str}\n"
                            f"Mint: `{mint[:8]}...`"
                        )
                        break
                
                if not found:
                    await self.send_message(
                        f"❌ Token {symbol} tidak ditemukan\n\n"
                        f"Gunakan /positions untuk lihat token yang ada"
                    )
                    return
            
            logger.info(f"TP set: {args}")
            
        except ValueError:
            await self.send_message("❌ Invalid number. Example: /settp 50 atau /settp DBULL 30")

    async def cmd_setsl(self, args: list):
        """Handle /setsl command - set stop loss (global or per-token)"""
        if not args:
            await self.send_message(
                "❌ *Usage:*\n"
                "`/setsl <percent>` → Set SL global\n"
                "`/setsl <symbol> <percent>` → Set SL per token\n\n"
                "*Example:*\n"
                "`/setsl 30` → Semua token auto sell -30%\n"
                "`/setsl DBULL 20` → DBULL auto sell -20%\n"
                "`/setsl Himgajria 50` → Himgajria auto sell -50%"
            )
            return
        
        try:
            # Check if first arg is a number (global) or symbol (per-token)
            if len(args) == 1:
                # Global SL
                sl = float(args[0])
                if sl <= 0:
                    await self.send_message("❌ SL harus lebih dari 0%")
                    return
                
                self.stop_loss = sl
                self.auto_trade = True
                
                tp_str = f"+{self.take_profit}%" if self.take_profit else "Not set"
                await self.send_message(
                    f"✅ *Global Stop Loss Set!*\n\n"
                    f"📈 TP: {tp_str}\n"
                    f"📉 SL: -{sl}% (semua token)\n"
                    f"🤖 Auto Trade: ON"
                )
            else:
                # Per-token SL
                symbol = args[0].upper()
                sl = float(args[1])
                if sl <= 0:
                    await self.send_message("❌ SL harus lebih dari 0%")
                    return
                
                # Find token by symbol
                found = False
                for mint, pos in self.positions.items():
                    if pos.get("symbol", "").upper() == symbol:
                        pos["sl"] = sl
                        pos["sl_executed"] = False
                        found = True
                        self.auto_trade = True
                        
                        tp_str = f"+{pos.get('tp')}%" if pos.get('tp') else "Global"
                        await self.send_message(
                            f"✅ *Stop Loss Set for {pos['symbol']}!*\n\n"
                            f"📈 TP: {tp_str}\n"
                            f"📉 SL: -{sl}%\n"
                            f"Mint: `{mint[:8]}...`"
                        )
                        break
                
                if not found:
                    await self.send_message(
                        f"❌ Token {symbol} tidak ditemukan\n\n"
                        f"Gunakan /positions untuk lihat token yang ada"
                    )
                    return
            
            logger.info(f"SL set: {args}")
            
        except ValueError:
            await self.send_message("❌ Invalid number. Example: /setsl 30 atau /setsl DBULL 20")

    async def cmd_cleartp(self):
        """Handle /cleartp command"""
        self.take_profit = None
        if not self.stop_loss:
            self.auto_trade = False
        await self.send_message("✅ Take Profit cleared")

    async def cmd_clearsl(self):
        """Handle /clearsl command"""
        self.stop_loss = None
        if not self.take_profit:
            self.auto_trade = False
        await self.send_message("✅ Stop Loss cleared")

    async def cmd_positions(self):
        """Handle /positions command"""
        if not self.positions:
            # Fetch fresh positions
            await self.check_positions()
        
        if not self.positions:
            await self.send_message("📭 No token positions found in wallet")
            return
        
        msg = "📊 *Your Positions*\n\n"
        total_value_usd = 0
        total_invested = 0
        total_pnl = 0
        
        for mint, pos in self.positions.items():
            symbol = pos.get("symbol", "UNKNOWN")
            amount = pos.get("amount", 0)
            invested_usd = pos.get("invested_usd", 0)
            entry_price_usd = pos.get("entry_price_usd", 0)
            
            # Get market data from DexScreener
            market_data = await self._get_dexscreener_data(mint)
            
            if market_data:
                price_usd = float(market_data.get("priceUsd", 0) or 0)
                change_24h = market_data.get("priceChange", {}).get("h24", 0)
                value_usd = amount * price_usd
                total_value_usd += value_usd
                
                # Calculate PnL if invested amount is set
                if invested_usd and invested_usd > 0:
                    pnl_usd = value_usd - invested_usd
                    pnl_percent = (pnl_usd / invested_usd) * 100
                    pnl_emoji = "🟢" if pnl_percent >= 0 else "🔴"
                    pnl_str = f"{pnl_percent:+.1f}% (${pnl_usd:+.2f})"
                    total_invested += invested_usd
                    total_pnl += pnl_usd
                    
                    msg += (
                        f"{pnl_emoji} *{symbol}*\n"
                        f"   Value: ${value_usd:.2f}\n"
                        f"   Invested: ${invested_usd:.2f}\n"
                        f"   *PnL: {pnl_str}*\n"
                        f"   Mint: `{mint[:8]}...`\n\n"
                    )
                else:
                    # No invested set - show 24h change
                    change_str = f"{float(change_24h):+.1f}%" if change_24h else "N/A"
                    pnl_emoji = "🟢" if change_24h and float(change_24h) >= 0 else "🔴" if change_24h else "⚪"
                    
                    msg += (
                        f"{pnl_emoji} *{symbol}*\n"
                        f"   Value: ${value_usd:.2f}\n"
                        f"   24h: {change_str}\n"
                        f"   💡 /setinvested {symbol} <usd>\n"
                        f"   Mint: `{mint[:8]}...`\n\n"
                    )
            else:
                msg += (
                    f"⚪ *{symbol}*\n"
                    f"   Amount: {amount:,.2f}\n"
                    f"   Price: N/A\n"
                    f"   Mint: `{mint[:8]}...`\n\n"
                )
        
        # Summary
        msg += "━━━━━━━━━━━━━━━\n"
        msg += f"💰 *Value: ${total_value_usd:.2f}*\n"
        if total_invested > 0:
            total_pnl_pct = (total_pnl / total_invested) * 100
            pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
            msg += f"📈 Invested: ${total_invested:.2f}\n"
            msg += f"{pnl_emoji} *PnL: {total_pnl_pct:+.1f}% (${total_pnl:+.2f})*"
        
        await self.send_message(msg)
    
    async def _get_dexscreener_data(self, mint: str) -> dict:
        """Get market data from DexScreener"""
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        return pairs[0]
            return {}
        except Exception as e:
            logger.warning(f"DexScreener fetch failed: {e}")
            return {}

    async def cmd_setentry(self, args: list):
        """Set entry price for a token (for PnL calculation)"""
        if len(args) < 2:
            await self.send_message(
                "❌ *Usage:* /setentry <mint> <price_usd>\n\n"
                "*Example:*\n"
                "`/setentry H1adb 0.0001` → Set entry $0.0001\n\n"
                "Use /positions to see mint addresses"
            )
            return
        
        mint_prefix = args[0]
        try:
            entry_price = float(args[1])
        except ValueError:
            await self.send_message("❌ Invalid price format")
            return
        
        # Find matching mint
        target_mint = None
        for mint in self.positions:
            if mint.startswith(mint_prefix) or mint_prefix in mint:
                target_mint = mint
                break
        
        if not target_mint:
            await self.send_message(f"❌ Position not found for: {mint_prefix}")
            return
        
        self.positions[target_mint]["entry_price_usd"] = entry_price
        symbol = self.positions[target_mint].get("symbol", "UNKNOWN")
        
        await self.send_message(
            f"✅ Entry price set!\n\n"
            f"Token: {symbol}\n"
            f"Entry: ${entry_price}\n"
            f"Mint: `{target_mint[:8]}...`"
        )

    async def cmd_setinvested(self, args: list):
        """Set invested amount for a token (auto-calculate entry price)"""
        if len(args) < 2:
            await self.send_message(
                "❌ *Usage:* /setinvested <mint> <amount_usd>\n\n"
                "*Example:*\n"
                "`/setinvested DBULL 1.13` → Invested $1.13\n"
                "`/setinvested H1adb 1.13` → Invested $1.13\n\n"
                "Bot akan auto-calculate entry price dari invested amount"
            )
            return
        
        mint_prefix = args[0].upper()
        try:
            invested = float(args[1])
        except ValueError:
            await self.send_message("❌ Invalid amount format")
            return
        
        # Find matching mint by symbol or mint prefix
        target_mint = None
        for mint, pos in self.positions.items():
            symbol = pos.get("symbol", "").upper()
            if symbol == mint_prefix or mint.startswith(mint_prefix) or mint_prefix in mint:
                target_mint = mint
                break
        
        if not target_mint:
            await self.send_message(f"❌ Position not found for: {mint_prefix}")
            return
        
        amount = self.positions[target_mint].get("amount", 0)
        if amount <= 0:
            await self.send_message("❌ Token amount is 0")
            return
        
        # Calculate entry price from invested amount
        entry_price = invested / amount
        
        self.positions[target_mint]["invested_usd"] = invested
        self.positions[target_mint]["entry_price_usd"] = entry_price
        symbol = self.positions[target_mint].get("symbol", "UNKNOWN")
        
        await self.send_message(
            f"✅ Invested amount set!\n\n"
            f"Token: {symbol}\n"
            f"Invested: ${invested:.2f}\n"
            f"Amount: {amount:,.2f}\n"
            f"Entry Price: ${entry_price:.10f}\n"
            f"Mint: `{target_mint[:8]}...`"
        )

    async def cmd_refresh(self):
        """Refresh all position data"""
        await self.send_message("🔄 Refreshing positions...")
        self.positions = {}  # Clear cache
        await self.check_positions()
        await self.cmd_positions()

    async def cmd_buy(self, args: list):
        """Handle /buy command - buy a token"""
        if len(args) < 2:
            await self.send_message(
                "❌ *Usage:* /buy <symbol_or_mint> <sol_amount>\n\n"
                "*Example:*\n"
                "`/buy DBULL 0.1` → Buy 0.1 SOL worth DBULL\n"
                "`/buy ABC123...xyz 0.1` → Buy by mint address\n\n"
                "Supports bonding curve & graduated tokens"
            )
            return
        
        symbol_or_mint = args[0]
        try:
            sol_amount = float(args[1])
            if sol_amount <= 0:
                await self.send_message("❌ Amount harus lebih dari 0")
                return
        except ValueError:
            await self.send_message("❌ Invalid amount")
            return
        
        # Try to find mint address from symbol
        mint = symbol_or_mint
        token_name = symbol_or_mint
        is_graduated = False
        
        # Check if it's a symbol (short) rather than mint address (long)
        if len(symbol_or_mint) < 30:
            # Search in current positions
            for m, pos in self.positions.items():
                if pos.get("symbol", "").upper() == symbol_or_mint.upper():
                    mint = m
                    token_name = pos.get("symbol", symbol_or_mint)
                    is_graduated = not pos.get("is_pump_active", False)
                    break
        
        # Check if token is graduated (not on pump.fun bonding curve anymore)
        token_info = await self.get_pump_token_info(mint)
        if not token_info:
            is_graduated = True
        
        pool_info = "(graduated → Raydium)" if is_graduated else "(bonding curve)"
        await self.send_message(
            f"🔄 *Buying {token_name}...* {pool_info}\n\n"
            f"Mint: `{mint[:12]}...`\n"
            f"Amount: {sol_amount} SOL"
        )
        
        success = await self.execute_buy(mint, sol_amount)
        
        if success:
            await self.send_message(
                f"✅ *Buy order executed!*\n\n"
                f"Token: {token_name}\n"
                f"Amount: {sol_amount} SOL\n"
                f"Use /refresh to see new position"
            )
        else:
            await self.send_message(
                f"❌ *Buy failed*\n\n"
                f"Possible reasons:\n"
                f"• Insufficient SOL balance\n"
                f"• Invalid mint address\n"
                f"• API error\n\n"
                f"Try manual buy:\n"
                f"• pump.fun: https://pump.fun/{mint}\n"
                f"• Jupiter: https://jup.ag"
            )

    async def cmd_limitbuy(self, args: list):
        """Handle /limitbuy command - set limit buy order"""
        if len(args) < 3:
            await self.send_message(
                "❌ *Usage:* /limitbuy <mint> <target_price_usd> <sol_amount>\n\n"
                "*Example:*\n"
                "`/limitbuy DBULL 0.00003 0.05`\n"
                "→ Buy 0.05 SOL worth DBULL when price drops to $0.00003\n\n"
                "`/limitbuy ABC123...xyz 0.0001 0.1`\n"
                "→ Buy by mint address\n\n"
                "Bot akan monitor dan auto buy saat harga tercapai"
            )
            return
        
        symbol_or_mint = args[0]
        try:
            target_price = float(args[1])
            sol_amount = float(args[2])
            if target_price <= 0 or sol_amount <= 0:
                await self.send_message("❌ Price dan amount harus lebih dari 0")
                return
        except ValueError:
            await self.send_message("❌ Invalid number format")
            return
        
        # Try to find mint address from symbol
        mint = symbol_or_mint
        token_name = symbol_or_mint
        
        if len(symbol_or_mint) < 30:
            # Search in current positions
            for m, pos in self.positions.items():
                if pos.get("symbol", "").upper() == symbol_or_mint.upper():
                    mint = m
                    token_name = pos.get("symbol", symbol_or_mint)
                    break
            else:
                # Not in positions, try to get from DexScreener
                token_name = symbol_or_mint.upper()
        
        # Get current price to compare
        dex_data = await self._get_dexscreener_data(mint)
        current_price = float(dex_data.get("priceUsd", 0)) if dex_data else 0
        
        if current_price > 0 and current_price <= target_price:
            await self.send_message(
                f"⚠️ *Current price ${current_price:.8f} sudah di bawah target ${target_price:.8f}*\n\n"
                f"Gunakan /buy untuk beli sekarang, atau set target lebih rendah."
            )
            return
        
        # Create limit order
        import datetime
        order_id = self.next_order_id
        self.next_order_id += 1
        
        self.limit_orders[order_id] = {
            "mint": mint,
            "symbol": token_name,
            "target_price": target_price,
            "sol_amount": sol_amount,
            "created_at": datetime.datetime.now().isoformat(),
        }
        
        price_diff = ((target_price - current_price) / current_price * 100) if current_price > 0 else 0
        
        await self.send_message(
            f"✅ *Limit Buy Order Created!*\n\n"
            f"Order ID: #{order_id}\n"
            f"Token: {token_name}\n"
            f"Target: ${target_price:.8f}\n"
            f"Amount: {sol_amount} SOL\n"
            f"Current: ${current_price:.8f} ({price_diff:+.1f}%)\n\n"
            f"Bot akan auto buy saat harga mencapai target.\n"
            f"Use /limits untuk lihat orders, /cancellimit {order_id} untuk cancel."
        )
        logger.info(f"Limit order #{order_id} created: {token_name} @ ${target_price}")

    async def cmd_limits(self):
        """Handle /limits command - show all pending limit orders"""
        if not self.limit_orders:
            await self.send_message("📭 Tidak ada limit order pending")
            return
        
        msg = "📋 *Pending Limit Orders:*\n\n"
        
        for order_id, order in self.limit_orders.items():
            # Get current price
            dex_data = await self._get_dexscreener_data(order["mint"])
            current_price = float(dex_data.get("priceUsd", 0)) if dex_data else 0
            
            target = order["target_price"]
            diff = ((current_price - target) / target * 100) if target > 0 else 0
            
            msg += (
                f"*#{order_id}* - {order['symbol']}\n"
                f"   Target: ${target:.8f}\n"
                f"   Current: ${current_price:.8f} ({diff:+.1f}%)\n"
                f"   Amount: {order['sol_amount']} SOL\n"
                f"   Cancel: /cancellimit {order_id}\n\n"
            )
        
        msg += f"Total: {len(self.limit_orders)} order(s)"
        await self.send_message(msg)

    async def cmd_cancellimit(self, args: list):
        """Handle /cancellimit command - cancel a limit order"""
        if not args:
            await self.send_message(
                "❌ *Usage:* /cancellimit <order_id>\n\n"
                "*Example:*\n"
                "`/cancellimit 1` → Cancel order #1\n"
                "`/cancellimit all` → Cancel semua orders\n\n"
                "Use /limits untuk lihat order IDs"
            )
            return
        
        if args[0].lower() == "all":
            count = len(self.limit_orders)
            self.limit_orders.clear()
            await self.send_message(f"✅ Cancelled {count} limit order(s)")
            return
        
        try:
            order_id = int(args[0])
        except ValueError:
            await self.send_message("❌ Invalid order ID")
            return
        
        if order_id not in self.limit_orders:
            await self.send_message(f"❌ Order #{order_id} tidak ditemukan")
            return
        
        order = self.limit_orders.pop(order_id)
        await self.send_message(
            f"✅ *Limit Order Cancelled!*\n\n"
            f"Order ID: #{order_id}\n"
            f"Token: {order['symbol']}\n"
            f"Target was: ${order['target_price']:.8f}"
        )

    async def cmd_price(self, args: list):
        """Handle /price command - show detailed price info with market cap"""
        if not args:
            await self.send_message(
                "❌ *Usage:* /price <symbol_or_mint>\n\n"
                "*Example:*\n"
                "`/price DBULL`\n"
                "`/price H1adb...pump`\n\n"
                "Shows price, market cap, volume, etc."
            )
            return
        
        symbol_or_mint = args[0]
        mint = symbol_or_mint
        
        # Try to find mint from symbol
        if len(symbol_or_mint) < 30:
            for m, pos in self.positions.items():
                if pos.get("symbol", "").upper() == symbol_or_mint.upper():
                    mint = m
                    break
        
        # Get DexScreener data
        dex_data = await self._get_dexscreener_data(mint)
        
        if not dex_data:
            await self.send_message(f"❌ Token tidak ditemukan: {symbol_or_mint}")
            return
        
        # Extract data
        symbol = dex_data.get("baseToken", {}).get("symbol", symbol_or_mint)
        price_usd = float(dex_data.get("priceUsd", 0))
        price_sol = float(dex_data.get("priceNative", 0))
        market_cap = dex_data.get("marketCap", 0) or dex_data.get("fdv", 0)
        fdv = dex_data.get("fdv", 0)
        liquidity = dex_data.get("liquidity", {}).get("usd", 0)
        volume_24h = dex_data.get("volume", {}).get("h24", 0)
        change_24h = dex_data.get("priceChange", {}).get("h24", 0)
        
        # Format market cap
        def format_number(n):
            if n >= 1_000_000:
                return f"${n/1_000_000:.2f}M"
            elif n >= 1_000:
                return f"${n/1_000:.1f}K"
            else:
                return f"${n:.0f}"
        
        # Determine emoji
        change_emoji = "🟢" if change_24h and float(change_24h) >= 0 else "🔴"
        
        msg = (
            f"📊 *{symbol} Price Info*\n\n"
            f"💵 *Price:* ${price_usd:.10f}\n"
            f"◎ *SOL:* {price_sol:.10f}\n\n"
            f"📈 *Market Cap:* {format_number(market_cap) if market_cap else 'N/A'}\n"
            f"💰 *FDV:* {format_number(fdv) if fdv else 'N/A'}\n"
            f"💧 *Liquidity:* {format_number(liquidity) if liquidity else 'N/A'}\n"
            f"📊 *24h Volume:* {format_number(volume_24h) if volume_24h else 'N/A'}\n"
            f"{change_emoji} *24h Change:* {change_24h}%\n\n"
            f"Mint: `{mint[:12]}...`\n\n"
            f"🔗 [DexScreener](https://dexscreener.com/solana/{mint}) | "
            f"[Pump.fun](https://pump.fun/{mint})"
        )
        
        await self.send_message(msg)

    async def cmd_history(self, args: list):
        """Handle /history command - show trade history"""
        import datetime
        
        # Filter by days (default 7)
        days = 7
        if args:
            try:
                days = int(args[0])
            except ValueError:
                pass
        
        if not self.trade_history:
            await self.send_message("📭 Belum ada trade history")
            return
        
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        
        # Filter recent trades
        recent_trades = []
        for trade in self.trade_history:
            try:
                trade_time = datetime.datetime.fromisoformat(trade["timestamp"])
                if trade_time >= cutoff:
                    recent_trades.append(trade)
            except:
                continue
        
        if not recent_trades:
            await self.send_message(f"📭 Tidak ada trades dalam {days} hari terakhir")
            return
        
        # Show last 10 trades
        msg = f"📜 *Trade History ({days} hari)*\n\n"
        
        for trade in recent_trades[-10:]:
            try:
                trade_time = datetime.datetime.fromisoformat(trade["timestamp"])
                date_str = trade_time.strftime("%d/%m %H:%M")
                
                emoji = "🟢" if trade["type"] == "buy" else "🔴"
                pnl_str = ""
                if trade["type"] == "sell" and trade.get("pnl_usd"):
                    pnl_emoji = "✅" if trade["pnl_usd"] >= 0 else "❌"
                    pnl_str = f" {pnl_emoji} ${trade['pnl_usd']:+.2f}"
                
                msg += f"{emoji} {date_str} | {trade['type'].upper()} {trade['symbol']}{pnl_str}\n"
            except:
                continue
        
        msg += f"\nTotal: {len(recent_trades)} trades\n"
        msg += f"Use /pnl untuk lihat realized PnL"
        
        await self.send_message(msg)

    async def cmd_pnl(self, args: list):
        """Handle /pnl command - show realized PnL"""
        import datetime
        
        # Default: today
        period = "today"
        if args:
            period = args[0].lower()
        
        now = datetime.datetime.now()
        
        if period == "today":
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_name = "Hari Ini"
        elif period == "week":
            cutoff = now - datetime.timedelta(days=7)
            period_name = "7 Hari"
        elif period == "month":
            cutoff = now - datetime.timedelta(days=30)
            period_name = "30 Hari"
        elif period == "all":
            cutoff = datetime.datetime(2020, 1, 1)
            period_name = "All Time"
        else:
            await self.send_message(
                "❌ *Usage:* /pnl [period]\n\n"
                "*Periods:*\n"
                "`/pnl today` → PnL hari ini\n"
                "`/pnl week` → PnL 7 hari\n"
                "`/pnl month` → PnL 30 hari\n"
                "`/pnl all` → PnL all time"
            )
            return
        
        if not self.trade_history:
            await self.send_message("📭 Belum ada trade history")
            return
        
        # Calculate PnL
        total_pnl = 0
        total_invested = 0
        total_received = 0
        sell_count = 0
        buy_count = 0
        winning_trades = 0
        losing_trades = 0
        
        # Group by token
        token_pnl = {}
        
        for trade in self.trade_history:
            try:
                trade_time = datetime.datetime.fromisoformat(trade["timestamp"])
                if trade_time < cutoff:
                    continue
                
                if trade["type"] == "sell":
                    sell_count += 1
                    pnl = trade.get("pnl_usd", 0)
                    total_pnl += pnl
                    total_invested += trade.get("invested_usd", 0)
                    total_received += trade.get("received_usd", 0)
                    
                    if pnl >= 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1
                    
                    symbol = trade.get("symbol", "UNKNOWN")
                    if symbol not in token_pnl:
                        token_pnl[symbol] = 0
                    token_pnl[symbol] += pnl
                    
                elif trade["type"] == "buy":
                    buy_count += 1
                    
            except:
                continue
        
        if sell_count == 0:
            await self.send_message(f"📭 Tidak ada sell trades dalam periode {period_name}")
            return
        
        # Calculate win rate
        win_rate = (winning_trades / sell_count * 100) if sell_count > 0 else 0
        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
        
        msg = (
            f"📊 *Realized PnL - {period_name}*\n\n"
            f"{pnl_emoji} *Total PnL:* ${total_pnl:+.2f}\n"
            f"💰 *Invested:* ${total_invested:.2f}\n"
            f"💵 *Received:* ${total_received:.2f}\n\n"
            f"📈 *Trades:*\n"
            f"• Buys: {buy_count}\n"
            f"• Sells: {sell_count}\n"
            f"• Wins: {winning_trades} | Losses: {losing_trades}\n"
            f"• Win Rate: {win_rate:.1f}%\n\n"
        )
        
        if token_pnl:
            msg += "*Per Token:*\n"
            for symbol, pnl in sorted(token_pnl.items(), key=lambda x: x[1], reverse=True):
                emoji = "🟢" if pnl >= 0 else "🔴"
                msg += f"{emoji} {symbol}: ${pnl:+.2f}\n"
        
        await self.send_message(msg)

    async def check_limit_orders(self):
        """Check and execute limit orders if price target reached"""
        if not self.limit_orders:
            return
        
        orders_to_remove = []
        
        for order_id, order in list(self.limit_orders.items()):
            try:
                # Get current price
                dex_data = await self._get_dexscreener_data(order["mint"])
                current_price = float(dex_data.get("priceUsd", 0)) if dex_data else 0
                
                if current_price <= 0:
                    continue
                
                # Check if price reached target (buy when price drops to target)
                if current_price <= order["target_price"]:
                    logger.info(f"🎯 Limit order #{order_id} triggered! Price ${current_price:.8f} <= ${order['target_price']:.8f}")
                    
                    await self.send_message(
                        f"🎯 *LIMIT ORDER TRIGGERED!*\n\n"
                        f"Order ID: #{order_id}\n"
                        f"Token: {order['symbol']}\n"
                        f"Target: ${order['target_price']:.8f}\n"
                        f"Current: ${current_price:.8f}\n"
                        f"Amount: {order['sol_amount']} SOL\n\n"
                        f"Executing buy..."
                    )
                    
                    # Execute buy
                    success = await self.execute_buy(order["mint"], order["sol_amount"])
                    
                    if success:
                        await self.send_message(
                            f"✅ *Limit Buy Executed!*\n\n"
                            f"Token: {order['symbol']}\n"
                            f"Price: ${current_price:.8f}\n"
                            f"Amount: {order['sol_amount']} SOL\n"
                            f"Use /refresh to see position"
                        )
                    else:
                        await self.send_message(
                            f"❌ *Limit Buy Failed!*\n\n"
                            f"Token: {order['symbol']}\n"
                            f"Try manual buy at pump.fun"
                        )
                    
                    orders_to_remove.append(order_id)
                    
            except Exception as e:
                logger.error(f"Error checking limit order #{order_id}: {e}")
        
        # Remove executed orders
        for order_id in orders_to_remove:
            self.limit_orders.pop(order_id, None)

    async def execute_buy(self, mint: str, sol_amount: float) -> bool:
        """Execute buy transaction via pumpportal API"""
        try:
            # Prepare buy request to pumpportal
            payload = {
                "publicKey": self.wallet_address,
                "action": "buy",
                "mint": mint,
                "amount": sol_amount,
                "denominatedInSol": "true",
                "slippage": 10,
                "priorityFee": 0.0001,
                "pool": "auto"
            }
            
            logger.info(f"Executing buy: {sol_amount} SOL of {mint}")
            
            async with self.session.post(
                self.PUMP_TRADE_API,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    tx_data = await response.read()
                    return await self._sign_and_send(tx_data)
                else:
                    error_text = await response.text()
                    logger.error(f"Buy API error: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Buy execution error: {e}")
            return False

    async def cmd_sell(self, args: list):
        """Handle /sell command"""
        if len(args) < 2:
            await self.send_message(
                "❌ Usage: /sell <mint> <percent>\n"
                "Example: /sell ABC123 50\n\n"
                "Use /positions to see mint addresses"
            )
            return
        
        mint_prefix = args[0]
        
        try:
            percent = float(args[1])
            if percent <= 0 or percent > 100:
                await self.send_message("❌ Percent harus 1-100")
                return
        except ValueError:
            await self.send_message("❌ Invalid percent")
            return
        
        # Find matching mint
        target_mint = None
        for mint in self.positions:
            if mint.startswith(mint_prefix) or mint_prefix in mint:
                target_mint = mint
                break
        
        if not target_mint:
            await self.send_message(f"❌ Position not found for: {mint_prefix}")
            return
        
        pos = self.positions[target_mint]
        amount_to_sell = pos["amount"] * (percent / 100)
        
        await self.send_message(
            f"🔄 Selling {percent}% of {pos['symbol']}...\n"
            f"Amount: {amount_to_sell:,.0f}"
        )
        
        success = await self.execute_sell(target_mint, amount_to_sell)
        
        if success:
            await self.send_message(f"✅ Sell executed for {pos['symbol']}")
        else:
            await self.send_message(f"❌ Sell failed for {pos['symbol']}")

    async def get_token_accounts(self) -> list:
        """Get all token accounts using Helius DAS API or fallback to multiple RPCs"""
        try:
            # If we have Helius API key, use DAS API (most reliable)
            if self.helius_api_key:
                result = await self._get_tokens_helius_das()
                if result:
                    return result
            
            # Try multiple RPCs as fallback
            rpcs = [
                os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com"),
                "https://api.mainnet-beta.solana.com",
            ]
            
            for rpc_url in rpcs:
                try:
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getTokenAccountsByOwner",
                        "params": [
                            self.wallet_address,
                            {"programId": self.TOKEN_PROGRAM_ID},
                            {"encoding": "jsonParsed"}
                        ]
                    }
                    
                    async with self.session.post(rpc_url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            data = await response.json()
                            if "error" not in data:
                                accounts = data.get("result", {}).get("value", [])
                                if accounts:
                                    logger.info(f"RPC {rpc_url} found {len(accounts)} accounts")
                                    return accounts
                except Exception as e:
                    logger.warning(f"RPC {rpc_url} failed: {e}")
                    continue
            
            return []
        except Exception as e:
            logger.error(f"Error getting token accounts: {e}")
            return []

    async def _get_tokens_helius_das(self) -> list:
        """Get tokens using Helius DAS API - more reliable"""
        try:
            url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAssetsByOwner",
                "params": {
                    "ownerAddress": self.wallet_address,
                    "page": 1,
                    "limit": 100,
                    "displayOptions": {
                        "showFungible": True,
                        "showNativeBalance": False
                    }
                }
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("result", {}).get("items", [])
                    
                    # Convert to standard format
                    accounts = []
                    for item in items:
                        if item.get("interface") == "FungibleToken":
                            token_info = item.get("token_info", {})
                            accounts.append({
                                "account": {
                                    "data": {
                                        "parsed": {
                                            "info": {
                                                "mint": item.get("id", ""),
                                                "tokenAmount": {
                                                    "uiAmount": token_info.get("balance", 0) / (10 ** token_info.get("decimals", 6)),
                                                    "decimals": token_info.get("decimals", 6)
                                                }
                                            }
                                        }
                                    }
                                },
                                "helius_data": item  # Keep original data
                            })
                    
                    logger.info(f"Helius DAS found {len(accounts)} fungible tokens")
                    return accounts
                else:
                    logger.error(f"Helius DAS error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error with Helius DAS: {e}")
            return []

    async def get_pump_token_info(self, mint: str) -> Optional[dict]:
        """Get token info from pump.fun"""
        try:
            url = f"{self.PUMP_API_BASE}/coins/{mint}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error getting pump token info: {e}")
            return None

    async def get_token_price_sol(self, mint: str) -> Optional[float]:
        """Get current token price in SOL - tries pump.fun first, then Jupiter"""
        # Try pump.fun bonding curve price first
        token_info = await self.get_pump_token_info(mint)
        if token_info:
            try:
                sol_reserves = float(token_info.get("virtual_sol_reserves", 0)) / 1e9
                token_reserves = float(token_info.get("virtual_token_reserves", 0)) / 1e6
                if token_reserves > 0:
                    price = sol_reserves / token_reserves
                    logger.debug(f"Got pump.fun price for {mint}: {price}")
                    return price
            except (ValueError, ZeroDivisionError):
                pass
        
        # Fallback to Jupiter API for graduated tokens
        try:
            jup_price = await self._get_jupiter_price_sol(mint)
            if jup_price:
                logger.debug(f"Got Jupiter price for {mint}: {jup_price}")
                return jup_price
        except Exception as e:
            logger.warning(f"Jupiter price fetch failed: {e}")
        
        return None

    async def _get_jupiter_price_sol(self, mint: str) -> Optional[float]:
        """Get token price from Jupiter API or DexScreener (in SOL)"""
        # Try Jupiter first
        try:
            url = f"https://api.jup.ag/price/v2?ids={mint}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    token_data = data.get("data", {}).get(mint, {})
                    usd_price = token_data.get("price")
                    
                    if usd_price:
                        # Get SOL price to convert
                        sol_mint = "So11111111111111111111111111111111111111112"
                        sol_url = f"https://api.jup.ag/price/v2?ids={sol_mint}"
                        async with self.session.get(sol_url) as sol_resp:
                            if sol_resp.status == 200:
                                sol_data = await sol_resp.json()
                                sol_usd = sol_data.get("data", {}).get(sol_mint, {}).get("price")
                                if sol_usd and float(sol_usd) > 0:
                                    return float(usd_price) / float(sol_usd)
        except Exception as e:
            logger.debug(f"Jupiter API failed: {e}")
        
        # Fallback to DexScreener
        try:
            url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get("pairs", [])
                    if pairs:
                        # Get first pair - priceNative is already in SOL
                        price_native = pairs[0].get("priceNative")
                        if price_native:
                            logger.info(f"Got DexScreener price: {price_native} SOL")
                            return float(price_native)
        except Exception as e:
            logger.debug(f"DexScreener API failed: {e}")
        
        return None

    async def check_positions(self):
        """Check positions and execute TP/SL if set"""
        token_accounts = await self.get_token_accounts()
        
        for account in token_accounts:
            try:
                parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                info = parsed.get("info", {})
                
                mint = info.get("mint", "")
                token_amount_info = info.get("tokenAmount", {})
                amount = float(token_amount_info.get("uiAmount", 0) or 0)
                
                if amount <= 0:
                    continue
                
                # Get token metadata - try pump.fun first, fallback to Helius DAS data
                token_info = await self.get_pump_token_info(mint)
                helius_data = account.get("helius_data", {})
                
                # Get symbol from pump.fun or Helius
                if token_info:
                    symbol = token_info.get("symbol", "UNKNOWN")
                    is_pump_active = True
                elif helius_data:
                    # Token might be graduated from pump.fun, use Helius metadata
                    metadata = helius_data.get("content", {}).get("metadata", {})
                    symbol = metadata.get("symbol", "UNKNOWN")
                    is_pump_active = False
                    logger.info(f"Token {symbol} detected from Helius (may be graduated)")
                else:
                    # Skip unknown tokens
                    continue
                
                # Get price - for graduated tokens, price might not be available
                current_price = await self.get_token_price_sol(mint)
                
                # Track new position (even if price not available for graduated tokens)
                if mint not in self.positions:
                    self.positions[mint] = {
                        "entry_price": current_price if current_price else 0,
                        "amount": amount,
                        "symbol": symbol,
                        "tp_executed": False,
                        "sl_executed": False,
                        "is_pump_active": is_pump_active,
                    }
                    
                    price_str = f"{current_price:.10f} SOL" if current_price else "N/A (graduated)"
                    await self.send_message(
                        f"📌 *New Position Detected*\n\n"
                        f"Token: {symbol}\n"
                        f"Amount: {amount:,.0f}\n"
                        f"Price: {price_str}\n"
                        f"Mint: `{mint[:12]}...`"
                    )
                    continue
                
                # Update amount and is_pump_active
                self.positions[mint]["amount"] = amount
                self.positions[mint]["is_pump_active"] = is_pump_active
                
                # Skip TP/SL check if price not available
                if current_price is None:
                    continue
                
                # Get DexScreener data for USD price
                dex_data = await self._get_dexscreener_data(mint)
                price_usd = float(dex_data.get("priceUsd", 0)) if dex_data else 0
                
                # Calculate P&L from invested USD (if set)
                invested_usd = self.positions[mint].get("invested_usd", 0)
                if invested_usd > 0 and price_usd > 0:
                    current_value_usd = amount * price_usd
                    pnl_usd = current_value_usd - invested_usd
                    pnl_percent = (pnl_usd / invested_usd) * 100
                else:
                    # Fallback to SOL price calculation
                    entry_price = self.positions[mint].get("entry_price", 0)
                    if entry_price <= 0:
                        continue
                    pnl_percent = ((current_price - entry_price) / entry_price) * 100
                
                symbol = self.positions[mint].get("symbol", "UNKNOWN")
                
                # Get TP/SL - per-token first, fallback to global
                token_tp = self.positions[mint].get("tp", self.take_profit)
                token_sl = self.positions[mint].get("sl", self.stop_loss)
                
                # Check TP
                if (self.auto_trade and 
                    token_tp and 
                    pnl_percent >= token_tp and 
                    not self.positions[mint].get("tp_executed", False)):
                    
                    logger.info(f"🟢 TP triggered for {symbol}: {pnl_percent:.2f}%")
                    
                    pool_info = "(graduated → Raydium)" if not is_pump_active else "(bonding curve)"
                    tp_type = "token" if self.positions[mint].get("tp") else "global"
                    await self.send_message(
                        f"🟢 *TAKE PROFIT TRIGGERED!*\n\n"
                        f"Token: {symbol} {pool_info}\n"
                        f"P&L: +{pnl_percent:.2f}%\n"
                        f"TP: +{token_tp}% ({tp_type})\n"
                        f"Executing sell..."
                    )
                    
                    success = await self.execute_sell(mint, amount)
                    self.positions[mint]["tp_executed"] = True
                    
                    if success:
                        # Record trade to history
                        invested = self.positions[mint].get("invested_usd", 0)
                        pnl_usd_val = (invested * pnl_percent / 100) if invested > 0 else 0
                        self._record_trade(
                            trade_type="sell",
                            symbol=symbol,
                            mint=mint,
                            amount_tokens=amount,
                            amount_sol=current_price * amount,
                            price_usd=price_usd,
                            invested_usd=invested,
                            pnl_usd=pnl_usd_val,
                            pnl_percent=pnl_percent
                        )
                        await self.send_message(f"✅ TP Sell executed for {symbol}")
                    else:
                        await self.send_message(
                            f"❌ TP Sell failed for {symbol}\n\n"
                            f"Sell manual di:\n"
                            f"• pump.fun: https://pump.fun/{mint}\n"
                            f"• Jupiter: https://jup.ag"
                        )
                
                # Check SL
                if (self.auto_trade and 
                    token_sl and 
                    pnl_percent <= -token_sl and 
                    not self.positions[mint].get("sl_executed", False)):
                    
                    logger.info(f"🔴 SL triggered for {symbol}: {pnl_percent:.2f}%")
                    
                    pool_info = "(graduated → Raydium)" if not is_pump_active else "(bonding curve)"
                    sl_type = "token" if self.positions[mint].get("sl") else "global"
                    await self.send_message(
                        f"🔴 *STOP LOSS TRIGGERED!*\n\n"
                        f"Token: {symbol} {pool_info}\n"
                        f"P&L: {pnl_percent:.2f}%\n"
                        f"SL: -{token_sl}% ({sl_type})\n"
                        f"Executing sell..."
                    )
                    
                    success = await self.execute_sell(mint, amount)
                    self.positions[mint]["sl_executed"] = True
                    
                    if success:
                        # Record trade to history
                        invested = self.positions[mint].get("invested_usd", 0)
                        pnl_usd_val = (invested * pnl_percent / 100) if invested > 0 else 0
                        self._record_trade(
                            trade_type="sell",
                            symbol=symbol,
                            mint=mint,
                            amount_tokens=amount,
                            amount_sol=current_price * amount,
                            price_usd=price_usd,
                            invested_usd=invested,
                            pnl_usd=pnl_usd_val,
                            pnl_percent=pnl_percent
                        )
                        await self.send_message(f"✅ SL Sell executed for {symbol}")
                    else:
                        await self.send_message(
                            f"❌ SL Sell failed for {symbol}\n\n"
                            f"Sell manual di:\n"
                            f"• pump.fun: https://pump.fun/{mint}\n"
                            f"• Jupiter: https://jup.ag"
                        )
                        
            except Exception as e:
                logger.error(f"Error processing token: {e}")

    async def execute_sell(self, mint: str, amount: float) -> bool:
        """Execute sell transaction via pumpportal API"""
        if not self.private_key:
            logger.warning("No private key - cannot execute")
            return False
        
        try:
            # Convert amount to percentage string for pumpportal API
            # This works better than raw token amounts
            if isinstance(amount, str) and '%' in amount:
                amount_str = amount  # Already percentage format
            else:
                # Calculate percentage of position
                position = self.positions.get(mint, {})
                total_amount = position.get("amount", amount)
                if total_amount > 0:
                    percentage = (amount / total_amount) * 100
                    amount_str = f"{int(percentage)}%"
                else:
                    amount_str = "100%"
            
            # Use pool: "auto" to support both bonding curve and graduated (Raydium) tokens
            payload = {
                "publicKey": self.wallet_address,
                "action": "sell",
                "mint": mint,
                "amount": amount_str,
                "denominatedInSol": "false",
                "slippage": 15,
                "priorityFee": 0.001,
                "pool": "auto"  # auto-route to pump or raydium
            }
            
            logger.info(f"Executing sell: {amount_str} of {mint}")
            
            async with self.session.post(self.PUMP_TRADE_API, json=payload) as response:
                if response.status == 200:
                    tx_data = await response.read()
                    return await self._sign_and_send(tx_data)
                else:
                    error = await response.text()
                    logger.error(f"Trade API error: {error}")
                    return False
                    
        except Exception as e:
            logger.error(f"Execute sell error: {e}")
            return False

    async def _sign_and_send(self, tx_bytes: bytes) -> bool:
        """Sign and send transaction"""
        try:
            from solders.keypair import Keypair
            from solders.transaction import VersionedTransaction
            from solders.message import to_bytes_versioned
            from solders.signature import Signature
            import base58
        except ImportError as e:
            logger.error(f"solders import error: {e}")
            await self.send_message("❌ Error: solders library not installed\nRun: pip install solders base58")
            return False
        
        try:
            # Handle hex format (64 chars = 32 bytes seed)
            if len(self.private_key) == 64:
                seed_bytes = bytes.fromhex(self.private_key)
                keypair = Keypair.from_seed(seed_bytes)
            else:
                keypair = Keypair.from_base58_string(self.private_key)
            
            # Deserialize the transaction
            tx = VersionedTransaction.from_bytes(tx_bytes)
            
            # Get message bytes to sign
            message_bytes = to_bytes_versioned(tx.message)
            
            # Sign the message
            signature = keypair.sign_message(message_bytes)
            
            # Create new transaction with signature
            # VersionedTransaction expects list of signatures in same order as accounts
            signed_tx = VersionedTransaction.populate(tx.message, [signature])
            
            rpc_url = f"{self.HELIUS_RPC}/?api-key={self.helius_api_key}" if self.helius_api_key else os.getenv("RPC_URL")
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [
                    base58.b58encode(bytes(signed_tx)).decode("utf-8"),
                    {"encoding": "base58", "skipPreflight": True}
                ]
            }
            
            async with self.session.post(rpc_url, json=payload) as response:
                result = await response.json()
                
                if "result" in result:
                    sig = result["result"]
                    logger.info(f"TX sent: {sig}")
                    await self.send_message(
                        f"✅ *Transaction Sent!*\n"
                        f"[View on Solscan](https://solscan.io/tx/{sig})"
                    )
                    return True
                else:
                    error = result.get("error", {})
                    logger.error(f"TX failed: {error}")
                    return False
                    
        except Exception as e:
            logger.error(f"Sign/send error: {e}")
            return False

    async def send_message(self, text: str):
        """Send Telegram message"""
        if not self.telegram_token or not self.telegram_chat_id:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    logger.warning(f"Telegram send failed: {response.status}")
        except Exception as e:
            logger.error(f"Telegram error: {e}")


async def main():
    bot = PumpFunTelegramBot()
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        await bot.stop()


if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    asyncio.run(main())
