#!/usr/bin/env python3
"""
Pump.fun Auto TP/SL Bot
Bot untuk auto close position berdasarkan take profit dan stop loss percentage.

Wallet: DZPuFxBZ5s6h1uevPCTpsDbiLiToKmJGLPjprWFhhX6T
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from decimal import Decimal
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
        logging.FileHandler("logs/pumpfun_bot.log", mode="a"),
    ],
)
logger = logging.getLogger(__name__)


class PumpFunBot:
    """Bot untuk monitoring dan auto close position di pump.fun"""

    # Pump.fun API endpoints
    PUMP_API_BASE = "https://frontend-api.pump.fun"
    PUMP_TRADE_API = "https://pumpportal.fun/api/trade"
    
    # Solana RPC
    HELIUS_RPC = "https://mainnet.helius-rpc.com"
    
    # Token Program IDs
    TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    ASSOCIATED_TOKEN_PROGRAM = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL"

    def __init__(
        self,
        wallet_address: str,
        private_key: Optional[str] = None,
        take_profit_levels: list[float] = None,
        stop_loss_percent: float = 10.0,
        check_interval: int = 30,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ):
        """
        Initialize PumpFun Bot
        
        Args:
            wallet_address: Solana wallet address to monitor
            private_key: Private key for signing transactions (base58 encoded)
            take_profit_levels: List of TP percentages [5, 10, 15, 20, etc.]
            stop_loss_percent: Stop loss percentage (default 10%)
            check_interval: Check interval in seconds (default 30)
            telegram_bot_token: Telegram bot token for notifications
            telegram_chat_id: Telegram chat ID for notifications
        """
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.take_profit_levels = take_profit_levels or [5.0, 10.0, 15.0, 20.0, 25.0]
        self.stop_loss_percent = stop_loss_percent
        self.check_interval = check_interval
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        
        # Position tracking
        # Format: {token_mint: {"entry_price": float, "amount": float, "tp_triggered": set()}}
        self.positions: dict = {}
        
        # Session for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Running flag
        self.running = False
        
        # Helius API key
        self.helius_api_key = os.getenv("HELIUS_API_KEY", "")
        
        logger.info(f"PumpFun Bot initialized for wallet: {wallet_address}")
        logger.info(f"TP Levels: {self.take_profit_levels}%")
        logger.info(f"SL Level: {self.stop_loss_percent}%")

    async def start(self):
        """Start the bot"""
        self.running = True
        self.session = aiohttp.ClientSession()
        
        logger.info("🚀 PumpFun Bot started!")
        await self.send_telegram_notification("🚀 PumpFun Bot started!\n\n"
            f"Wallet: `{self.wallet_address[:8]}...{self.wallet_address[-4:]}`\n"
            f"TP Levels: {self.take_profit_levels}%\n"
            f"SL Level: {self.stop_loss_percent}%")
        
        try:
            while self.running:
                await self.check_positions()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("Bot cancelled")
        finally:
            await self.stop()

    async def stop(self):
        """Stop the bot"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("🛑 PumpFun Bot stopped")
        await self.send_telegram_notification("🛑 PumpFun Bot stopped")

    async def get_token_accounts(self) -> list[dict]:
        """
        Get all token accounts for the wallet
        
        Returns:
            List of token account data
        """
        try:
            rpc_url = f"{self.HELIUS_RPC}/?api-key={self.helius_api_key}" if self.helius_api_key else os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
            
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
            
            async with self.session.post(rpc_url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data and "value" in data["result"]:
                        return data["result"]["value"]
                    return []
                else:
                    logger.error(f"RPC error: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error getting token accounts: {e}")
            return []

    async def get_pump_token_info(self, mint_address: str) -> Optional[dict]:
        """
        Get token info from pump.fun API
        
        Args:
            mint_address: Token mint address
            
        Returns:
            Token info dict or None
        """
        try:
            url = f"{self.PUMP_API_BASE}/coins/{mint_address}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error getting pump token info: {e}")
            return None

    async def get_token_price_sol(self, mint_address: str) -> Optional[float]:
        """
        Get current token price in SOL from pump.fun
        
        Args:
            mint_address: Token mint address
            
        Returns:
            Price in SOL or None
        """
        token_info = await self.get_pump_token_info(mint_address)
        if token_info:
            # Pump.fun returns virtual_sol_reserves and virtual_token_reserves
            # Price = sol_reserves / token_reserves
            try:
                sol_reserves = float(token_info.get("virtual_sol_reserves", 0)) / 1e9
                token_reserves = float(token_info.get("virtual_token_reserves", 0)) / 1e6
                if token_reserves > 0:
                    return sol_reserves / token_reserves
            except (ValueError, ZeroDivisionError):
                pass
        return None

    async def check_positions(self):
        """Check all positions and execute TP/SL if needed"""
        logger.info("📊 Checking positions...")
        
        token_accounts = await self.get_token_accounts()
        
        for account in token_accounts:
            try:
                parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                info = parsed.get("info", {})
                
                mint = info.get("mint", "")
                token_amount_info = info.get("tokenAmount", {})
                amount = float(token_amount_info.get("uiAmount", 0) or 0)
                
                # Skip if no balance
                if amount <= 0:
                    continue
                
                # Check if this is a pump.fun token
                token_info = await self.get_pump_token_info(mint)
                if not token_info:
                    continue  # Not a pump.fun token
                
                symbol = token_info.get("symbol", "UNKNOWN")
                current_price = await self.get_token_price_sol(mint)
                
                if current_price is None:
                    logger.warning(f"Could not get price for {symbol}")
                    continue
                
                # Track new position if not already tracking
                if mint not in self.positions:
                    # First time seeing this position, record as entry
                    self.positions[mint] = {
                        "entry_price": current_price,
                        "amount": amount,
                        "symbol": symbol,
                        "tp_triggered": set(),
                        "entry_time": datetime.now().isoformat()
                    }
                    logger.info(f"📌 New position tracked: {symbol}")
                    logger.info(f"   Entry Price: {current_price:.10f} SOL")
                    logger.info(f"   Amount: {amount:,.2f}")
                    
                    await self.send_telegram_notification(
                        f"📌 New Position Tracked\n\n"
                        f"Token: {symbol}\n"
                        f"Mint: `{mint[:8]}...{mint[-4:]}`\n"
                        f"Entry Price: {current_price:.10f} SOL\n"
                        f"Amount: {amount:,.2f}"
                    )
                    continue
                
                # Calculate P&L
                position = self.positions[mint]
                entry_price = position["entry_price"]
                pnl_percent = ((current_price - entry_price) / entry_price) * 100
                
                logger.info(f"💰 {symbol}: {pnl_percent:+.2f}% (Current: {current_price:.10f} SOL)")
                
                # Check Stop Loss
                if pnl_percent <= -self.stop_loss_percent:
                    logger.warning(f"🔴 STOP LOSS triggered for {symbol}!")
                    await self.close_position(mint, amount, "STOP LOSS", pnl_percent)
                    continue
                
                # Check Take Profit levels
                for tp_level in self.take_profit_levels:
                    if tp_level not in position["tp_triggered"] and pnl_percent >= tp_level:
                        logger.info(f"🟢 Take Profit {tp_level}% triggered for {symbol}!")
                        position["tp_triggered"].add(tp_level)
                        
                        # Close a portion (e.g., 20% per TP level)
                        close_percent = 100 / len(self.take_profit_levels)
                        close_amount = amount * (close_percent / 100)
                        
                        await self.close_position(
                            mint, 
                            close_amount, 
                            f"TP {tp_level}%",
                            pnl_percent
                        )
                        
            except Exception as e:
                logger.error(f"Error processing token account: {e}")

    async def close_position(self, mint: str, amount: float, reason: str, pnl_percent: float):
        """
        Close position (sell tokens)
        
        Args:
            mint: Token mint address
            amount: Amount to sell
            reason: Reason for closing (TP/SL)
            pnl_percent: Current P&L percentage
        """
        position = self.positions.get(mint, {})
        symbol = position.get("symbol", "UNKNOWN")
        
        logger.info(f"🔄 Closing position: {symbol}")
        logger.info(f"   Reason: {reason}")
        logger.info(f"   Amount: {amount:,.2f}")
        logger.info(f"   P&L: {pnl_percent:+.2f}%")
        
        # Notification
        emoji = "🟢" if pnl_percent > 0 else "🔴"
        await self.send_telegram_notification(
            f"{emoji} {reason} - {symbol}\n\n"
            f"Mint: `{mint[:8]}...{mint[-4:]}`\n"
            f"Amount: {amount:,.2f}\n"
            f"P&L: {pnl_percent:+.2f}%\n"
            f"Entry: {position.get('entry_price', 0):.10f} SOL"
        )
        
        # Execute sell if private key is provided
        if self.private_key:
            success = await self.execute_sell(mint, amount)
            if success:
                logger.info(f"✅ Sell executed successfully for {symbol}")
            else:
                logger.error(f"❌ Sell failed for {symbol}")
        else:
            logger.warning("⚠️ No private key provided - DRY RUN mode")
            await self.send_telegram_notification(
                f"⚠️ DRY RUN - No actual trade executed\n"
                f"Add PRIVATE_KEY to .env to enable trading"
            )

    async def execute_sell(self, mint: str, amount: float) -> bool:
        """
        Execute sell transaction via pumpportal API
        
        Args:
            mint: Token mint address
            amount: Amount to sell
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Method 1: Using pumpportal.fun API (recommended)
            # This API creates and sends the transaction for you
            
            payload = {
                "publicKey": self.wallet_address,
                "action": "sell",
                "mint": mint,
                "amount": str(int(amount * 1e6)),  # Token amount in smallest unit
                "denominatedInSol": "false",
                "slippage": 15,  # 15% slippage for volatile tokens
                "priorityFee": 0.001,  # Priority fee in SOL
                "pool": "pump"
            }
            
            # If we have private key, we need to sign locally
            if self.private_key:
                # Get unsigned transaction from pumpportal
                async with self.session.post(
                    "https://pumpportal.fun/api/trade-local",
                    json=payload
                ) as response:
                    if response.status == 200:
                        tx_data = await response.read()
                        
                        # Sign and send transaction
                        success = await self._sign_and_send_transaction(tx_data)
                        return success
                    else:
                        error_text = await response.text()
                        logger.error(f"Pumpportal API error: {response.status} - {error_text}")
                        return False
            else:
                logger.warning("No private key - cannot execute trade")
                return False
                
        except Exception as e:
            logger.error(f"Error executing sell: {e}")
            return False

    async def _sign_and_send_transaction(self, tx_bytes: bytes) -> bool:
        """
        Sign and send a Solana transaction
        
        Args:
            tx_bytes: Unsigned transaction bytes
            
        Returns:
            True if successful
        """
        try:
            # Try to import solders for signing
            try:
                from solders.keypair import Keypair
                from solders.transaction import VersionedTransaction
                import base58
            except ImportError:
                logger.error("solders library not installed. Run: pip install solders")
                await self.send_telegram_notification(
                    "❌ Cannot execute trade - solders library not installed\n"
                    "Run: `pip install solders`"
                )
                return False
            
            # Decode private key
            keypair = Keypair.from_base58_string(self.private_key)
            
            # Deserialize and sign transaction
            tx = VersionedTransaction.from_bytes(tx_bytes)
            tx.sign([keypair])
            
            # Send transaction
            rpc_url = f"{self.HELIUS_RPC}/?api-key={self.helius_api_key}" if self.helius_api_key else os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendTransaction",
                "params": [
                    base58.b58encode(bytes(tx)).decode("utf-8"),
                    {"encoding": "base58", "skipPreflight": True, "maxRetries": 3}
                ]
            }
            
            async with self.session.post(rpc_url, json=payload) as response:
                result = await response.json()
                
                if "result" in result:
                    tx_sig = result["result"]
                    logger.info(f"✅ Transaction sent: {tx_sig}")
                    await self.send_telegram_notification(
                        f"✅ Trade executed!\n"
                        f"Signature: `{tx_sig[:16]}...`\n"
                        f"[View on Solscan](https://solscan.io/tx/{tx_sig})"
                    )
                    return True
                else:
                    error = result.get("error", {})
                    logger.error(f"Transaction failed: {error}")
                    await self.send_telegram_notification(
                        f"❌ Trade failed: {error.get('message', 'Unknown error')}"
                    )
                    return False
                    
        except Exception as e:
            logger.error(f"Error signing/sending transaction: {e}")
            await self.send_telegram_notification(f"❌ Transaction error: {str(e)[:100]}")
            return False

    async def send_telegram_notification(self, message: str):
        """
        Send notification to Telegram
        
        Args:
            message: Message to send
        """
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            async with self.session.post(url, json=payload) as response:
                if response.status != 200:
                    logger.warning(f"Telegram notification failed: {response.status}")
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")

    def add_manual_position(self, mint: str, entry_price: float, amount: float, symbol: str = ""):
        """
        Manually add a position with specific entry price
        
        Args:
            mint: Token mint address
            entry_price: Entry price in SOL
            amount: Amount of tokens
            symbol: Token symbol (optional)
        """
        self.positions[mint] = {
            "entry_price": entry_price,
            "amount": amount,
            "symbol": symbol,
            "tp_triggered": set(),
            "entry_time": datetime.now().isoformat()
        }
        logger.info(f"📌 Manual position added: {symbol or mint[:8]}")
        logger.info(f"   Entry Price: {entry_price:.10f} SOL")
        logger.info(f"   Amount: {amount:,.2f}")

    def update_tp_levels(self, levels: list[float]):
        """Update take profit levels"""
        self.take_profit_levels = sorted(levels)
        logger.info(f"TP Levels updated: {self.take_profit_levels}%")

    def update_sl_level(self, level: float):
        """Update stop loss level"""
        self.stop_loss_percent = level
        logger.info(f"SL Level updated: {self.stop_loss_percent}%")


async def main():
    """Main entry point"""
    # Configuration from environment
    # Support both PUMP_WALLET_ADDRESS and WALLET_ADDRESS (from existing .env)
    wallet_address = os.getenv("PUMP_WALLET_ADDRESS") or os.getenv("WALLET_ADDRESS", "DZPuFxBZ5s6h1uevPCTpsDbiLiToKmJGLPjprWFhhX6T")
    private_key = os.getenv("PUMP_PRIVATE_KEY")  # Optional - for actual trading
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    # TP/SL Configuration
    tp_levels = [5.0, 10.0, 15.0, 20.0, 25.0]
    sl_level = 10.0
    check_interval = 30  # seconds
    
    # Override from env if provided
    if os.getenv("TP_LEVELS"):
        tp_levels = [float(x.strip()) for x in os.getenv("TP_LEVELS").split(",")]
    if os.getenv("SL_LEVEL"):
        sl_level = float(os.getenv("SL_LEVEL"))
    if os.getenv("CHECK_INTERVAL"):
        check_interval = int(os.getenv("CHECK_INTERVAL"))
    
    bot = PumpFunBot(
        wallet_address=wallet_address,
        private_key=private_key,
        take_profit_levels=tp_levels,
        stop_loss_percent=sl_level,
        check_interval=check_interval,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
    )
    
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
        await bot.stop()


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Run the bot
    asyncio.run(main())
