#!/usr/bin/env python3
"""
Pump.fun Bot CLI
Interactive command-line interface untuk manage bot.
"""

import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment from .env or .env.pumpfun
if os.path.exists(".env.pumpfun"):
    load_dotenv(".env.pumpfun")
else:
    load_dotenv()

from pumpfun_bot import PumpFunBot


def print_banner():
    """Print banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║             🚀 PUMP.FUN AUTO TP/SL BOT 🚀                     ║
╠═══════════════════════════════════════════════════════════════╣
║  Auto close positions based on Take Profit & Stop Loss        ║
║  Website: https://pump.fun                                    ║
╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_config(args):
    """Print current configuration"""
    wallet = args.wallet or os.getenv("PUMP_WALLET_ADDRESS", "Not set")
    has_key = "✅" if (args.private_key or os.getenv("PUMP_PRIVATE_KEY")) else "❌ (DRY RUN)"
    
    print("\n📋 Current Configuration:")
    print(f"   Wallet: {wallet[:8]}...{wallet[-4:] if len(wallet) > 12 else wallet}")
    print(f"   Private Key: {has_key}")
    print(f"   TP Levels: {args.tp}%")
    print(f"   SL Level: {args.sl}%")
    print(f"   Check Interval: {args.interval}s")
    print(f"   Telegram: {'✅' if os.getenv('TELEGRAM_BOT_TOKEN') else '❌'}")
    print()


async def run_bot(args):
    """Run the bot with given arguments"""
    # Support both PUMP_WALLET_ADDRESS and WALLET_ADDRESS (from existing .env)
    wallet = args.wallet or os.getenv("PUMP_WALLET_ADDRESS") or os.getenv("WALLET_ADDRESS", "DZPuFxBZ5s6h1uevPCTpsDbiLiToKmJGLPjprWFhhX6T")
    private_key = args.private_key or os.getenv("PUMP_PRIVATE_KEY")
    
    tp_levels = [float(x.strip()) for x in args.tp.split(",")]
    sl_level = float(args.sl)
    
    bot = PumpFunBot(
        wallet_address=wallet,
        private_key=private_key,
        take_profit_levels=tp_levels,
        stop_loss_percent=sl_level,
        check_interval=args.interval,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )
    
    # Add manual positions if specified
    if args.positions:
        for pos in args.positions:
            parts = pos.split(":")
            if len(parts) >= 3:
                mint, entry_price, amount = parts[0], float(parts[1]), float(parts[2])
                symbol = parts[3] if len(parts) > 3 else ""
                bot.add_manual_position(mint, entry_price, amount, symbol)
    
    await bot.start()


async def check_positions(args):
    """One-time check positions without continuous monitoring"""
    # Support both PUMP_WALLET_ADDRESS and WALLET_ADDRESS (from existing .env)
    wallet = args.wallet or os.getenv("PUMP_WALLET_ADDRESS") or os.getenv("WALLET_ADDRESS", "DZPuFxBZ5s6h1uevPCTpsDbiLiToKmJGLPjprWFhhX6T")
    
    bot = PumpFunBot(
        wallet_address=wallet,
        check_interval=60,  # doesn't matter for one-time check
    )
    
    bot.session = await asyncio.to_thread(lambda: __import__("aiohttp").ClientSession())
    
    import aiohttp
    async with aiohttp.ClientSession() as session:
        bot.session = session
        
        print(f"\n📊 Checking positions for wallet: {wallet}\n")
        
        token_accounts = await bot.get_token_accounts()
        
        if not token_accounts:
            print("No token accounts found or RPC error.")
            return
        
        found_pump_tokens = False
        
        for account in token_accounts:
            try:
                parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                info = parsed.get("info", {})
                
                mint = info.get("mint", "")
                token_amount_info = info.get("tokenAmount", {})
                amount = float(token_amount_info.get("uiAmount", 0) or 0)
                
                if amount <= 0:
                    continue
                
                # Check if pump.fun token
                token_info = await bot.get_pump_token_info(mint)
                if not token_info:
                    continue
                
                found_pump_tokens = True
                symbol = token_info.get("symbol", "UNKNOWN")
                name = token_info.get("name", "Unknown")
                price = await bot.get_token_price_sol(mint)
                
                print(f"🪙 {symbol} ({name})")
                print(f"   Mint: {mint}")
                print(f"   Balance: {amount:,.2f}")
                if price:
                    print(f"   Price: {price:.10f} SOL")
                    value_sol = amount * price
                    print(f"   Value: {value_sol:.6f} SOL")
                print()
                
            except Exception as e:
                print(f"Error processing account: {e}")
        
        if not found_pump_tokens:
            print("No pump.fun tokens found in this wallet.")


def main():
    parser = argparse.ArgumentParser(
        description="Pump.fun Auto TP/SL Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings (from .env)
  python pumpfun_cli.py run

  # Run with custom TP/SL
  python pumpfun_cli.py run --tp 5,10,20,30 --sl 15

  # Check current positions
  python pumpfun_cli.py check

  # Run with specific wallet
  python pumpfun_cli.py run --wallet <ADDRESS>

  # Add manual position tracking
  python pumpfun_cli.py run --positions "MINT:0.000001:1000:SYMBOL"
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Start the bot")
    run_parser.add_argument("--wallet", "-w", help="Wallet address to monitor")
    run_parser.add_argument("--private-key", "-k", help="Private key for trading (base58)")
    run_parser.add_argument("--tp", default="5,10,15,20,25", help="Take profit levels (comma separated)")
    run_parser.add_argument("--sl", default="10", help="Stop loss percentage")
    run_parser.add_argument("--interval", "-i", type=int, default=30, help="Check interval in seconds")
    run_parser.add_argument("--positions", "-p", nargs="*", help="Manual positions (MINT:ENTRY:AMOUNT:SYMBOL)")
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Check current positions")
    check_parser.add_argument("--wallet", "-w", help="Wallet address to check")
    
    args = parser.parse_args()
    
    print_banner()
    
    if not args.command:
        parser.print_help()
        return
    
    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    if args.command == "run":
        print_config(args)
        
        print("🚀 Starting bot... Press Ctrl+C to stop.\n")
        
        try:
            asyncio.run(run_bot(args))
        except KeyboardInterrupt:
            print("\n\n👋 Bot stopped by user.")
    
    elif args.command == "check":
        try:
            asyncio.run(check_positions(args))
        except KeyboardInterrupt:
            print("\n\nCancelled.")


if __name__ == "__main__":
    main()
