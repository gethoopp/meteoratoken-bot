#!/usr/bin/env python3
"""
Meteora Portfolio Monitor Telegram Bot
Monitors DLMM and DAMM positions on Meteora DEX
"""

import os
import sys
import json
import time
import logging
import argparse
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from decimal import Decimal

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WALLET_ADDRESS = os.getenv("WALLET_ADDRESS", "")
RPC_URL = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SECONDS", "1200"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
USD_TO_IDR = float(os.getenv("USD_TO_IDR_RATE", "16100"))

# API Endpoints
METEORA_DLMM_API = "https://dlmm-api.meteora.ag"
METEORA_DAMM_API = "https://amm-v2.meteora.ag"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Position:
    """Represents a liquidity position"""
    address: str
    pool_address: str
    pair_name: str
    position_type: str  # "DLMM" or "DAMM"
    total_value_usd: float = 0.0
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    unclaimed_fees_usd: float = 0.0
    in_range: bool = True
    active_bin: int = 0
    lower_bin: int = 0
    upper_bin: int = 0
    bins_to_lower: int = 0
    bins_to_upper: int = 0
    token_x_symbol: str = ""
    token_y_symbol: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioSnapshot:
    """Snapshot of portfolio state"""
    timestamp: datetime
    total_value_usd: float
    total_pnl_usd: float
    total_pnl_pct: float
    total_fees_usd: float
    positions: List[Position]
    dlmm_count: int = 0
    damm_count: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def format_usd(value: float) -> str:
    """Format USD value"""
    if abs(value) >= 1000:
        return f"${value:,.2f}"
    return f"${value:.2f}"


def format_idr(usd_value: float) -> str:
    """Convert USD to IDR and format"""
    idr = usd_value * USD_TO_IDR
    if abs(idr) >= 1_000_000:
        return f"Rp {idr/1_000_000:.1f}jt"
    elif abs(idr) >= 1000:
        return f"Rp {idr:,.0f}"
    return f"Rp {idr:.0f}"


def format_pct(value: float) -> str:
    """Format percentage"""
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def pnl_emoji(pnl: float) -> str:
    """Get emoji based on PnL"""
    if pnl > 0:
        return "📈"
    elif pnl < 0:
        return "📉"
    return "➖"


def safe_get(data: dict, *keys, default=None):
    """Safely get nested dictionary value"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data if data is not None else default



# ═══════════════════════════════════════════════════════════════════════════════
# API FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class MeteoraAPI:
    """Meteora API client"""
    
    def __init__(self, wallet_address: str):
        self.wallet = wallet_address
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "MeteoraBot/1.0"
        })
    
    def fetch_dlmm_positions(self) -> List[Position]:
        """Fetch DLMM positions for wallet"""
        positions = []
        try:
            url = f"{METEORA_DLMM_API}/position/{self.wallet}"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            for item in data if isinstance(data, list) else []:
                pos = self._parse_dlmm_position(item)
                if pos:
                    positions.append(pos)
                    
        except Exception as e:
            logger.error(f"Error fetching DLMM positions: {e}")
        
        return positions
    
    def _parse_dlmm_position(self, data: dict) -> Optional[Position]:
        """Parse DLMM position data"""
        try:
            pair_info = safe_get(data, "pair", default={})
            pair_name = safe_get(pair_info, "name", default="Unknown")
            
            # Get position value and PnL
            total_value = float(safe_get(data, "totalValueUsd", default=0))
            pnl_usd = float(safe_get(data, "pnlUsd", default=0))
            pnl_pct = float(safe_get(data, "pnlPct", default=0))
            fees = float(safe_get(data, "unclaimedFeesUsd", default=0))
            
            # Bin info
            active_bin = int(safe_get(pair_info, "activeBinId", default=0))
            lower_bin = int(safe_get(data, "lowerBinId", default=0))
            upper_bin = int(safe_get(data, "upperBinId", default=0))
            
            in_range = lower_bin <= active_bin <= upper_bin if lower_bin and upper_bin else True
            bins_to_lower = active_bin - lower_bin if active_bin and lower_bin else 0
            bins_to_upper = upper_bin - active_bin if upper_bin and active_bin else 0
            
            return Position(
                address=safe_get(data, "address", default=""),
                pool_address=safe_get(pair_info, "address", default=""),
                pair_name=pair_name,
                position_type="DLMM",
                total_value_usd=total_value,
                pnl_usd=pnl_usd,
                pnl_pct=pnl_pct,
                unclaimed_fees_usd=fees,
                in_range=in_range,
                active_bin=active_bin,
                lower_bin=lower_bin,
                upper_bin=upper_bin,
                bins_to_lower=bins_to_lower,
                bins_to_upper=bins_to_upper,
                token_x_symbol=safe_get(pair_info, "mintX", "symbol", default=""),
                token_y_symbol=safe_get(pair_info, "mintY", "symbol", default=""),
                extra=data
            )
        except Exception as e:
            logger.error(f"Error parsing DLMM position: {e}")
            return None
    
    def fetch_damm_positions(self) -> List[Position]:
        """Fetch DAMM positions for wallet"""
        positions = []
        try:
            url = f"{METEORA_DAMM_API}/position/user_positions?user_address={self.wallet}"
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            
            for item in data if isinstance(data, list) else []:
                pos = self._parse_damm_position(item)
                if pos:
                    positions.append(pos)
                    
        except Exception as e:
            logger.error(f"Error fetching DAMM positions: {e}")
        
        return positions
    
    def _parse_damm_position(self, data: dict) -> Optional[Position]:
        """Parse DAMM position data"""
        try:
            pool_info = safe_get(data, "pool", default={})
            pair_name = safe_get(pool_info, "pool_name", default="Unknown")
            
            total_value = float(safe_get(data, "total_value_usd", default=0))
            pnl_usd = float(safe_get(data, "pnl_usd", default=0))
            pnl_pct = float(safe_get(data, "pnl_pct", default=0))
            fees = float(safe_get(data, "unclaimed_fee_usd", default=0))
            
            return Position(
                address=safe_get(data, "position_address", default=""),
                pool_address=safe_get(pool_info, "pool_address", default=""),
                pair_name=pair_name,
                position_type="DAMM",
                total_value_usd=total_value,
                pnl_usd=pnl_usd,
                pnl_pct=pnl_pct,
                unclaimed_fees_usd=fees,
                in_range=True,
                extra=data
            )
        except Exception as e:
            logger.error(f"Error parsing DAMM position: {e}")
            return None
    
    def fetch_portfolio(self) -> PortfolioSnapshot:
        """Fetch complete portfolio snapshot"""
        dlmm_positions = self.fetch_dlmm_positions()
        damm_positions = self.fetch_damm_positions()
        
        all_positions = dlmm_positions + damm_positions
        
        total_value = sum(p.total_value_usd for p in all_positions)
        total_pnl = sum(p.pnl_usd for p in all_positions)
        total_fees = sum(p.unclaimed_fees_usd for p in all_positions)
        total_pnl_pct = (total_pnl / total_value * 100) if total_value > 0 else 0
        
        return PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            total_value_usd=total_value,
            total_pnl_usd=total_pnl,
            total_pnl_pct=total_pnl_pct,
            total_fees_usd=total_fees,
            positions=all_positions,
            dlmm_count=len(dlmm_positions),
            damm_count=len(damm_positions)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TelegramBot:
    """Telegram bot for notifications"""
    
    def __init__(self, token: str, chat_id: str, dry_run: bool = False):
        self.token = token
        self.chat_id = chat_id
        self.dry_run = dry_run
        self.api_url = f"https://api.telegram.org/bot{token}"
    
    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram"""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would send message:\n{text}")
            return True
        
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured")
            return False
        
        try:
            resp = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True
                },
                timeout=30
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False


def build_summary_message(snapshot: PortfolioSnapshot) -> str:
    """Build periodic summary message"""
    emoji = pnl_emoji(snapshot.total_pnl_usd)
    
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━",
        "📊 METEORA PORTFOLIO",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💰 Balance   {format_usd(snapshot.total_value_usd)}",
        f"             {format_idr(snapshot.total_value_usd)}",
        f"{emoji} PnL       {format_usd(snapshot.total_pnl_usd)} ({format_pct(snapshot.total_pnl_pct)})",
        f"💸 Fees      {format_usd(snapshot.total_fees_usd)}",
        f"📍 Posisi    {len(snapshot.positions)} ({snapshot.dlmm_count} DLMM, {snapshot.damm_count} DAMM)",
        "",
    ]
    
    # Range status for DLMM
    dlmm_positions = [p for p in snapshot.positions if p.position_type == "DLMM"]
    if dlmm_positions:
        lines.append("───── 🎯 Range ─────")
        out_of_range = [p for p in dlmm_positions if not p.in_range]
        if out_of_range:
            for p in out_of_range[:3]:
                lines.append(f"⛔ {p.pair_name} — keluar range")
            if len(out_of_range) > 3:
                lines.append(f"   +{len(out_of_range)-3} lainnya")
        else:
            near_edge = [p for p in dlmm_positions if p.bins_to_lower <= 5 or p.bins_to_upper <= 5]
            if near_edge:
                for p in near_edge[:3]:
                    if p.bins_to_lower <= 5:
                        lines.append(f"⚠️ {p.pair_name} — dekat batas bawah ({p.bins_to_lower} bin)")
                    else:
                        lines.append(f"⚠️ {p.pair_name} — dekat batas atas ({p.bins_to_upper} bin)")
            else:
                lines.append("✅ Semua aman")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


def build_position_detail(pos: Position) -> str:
    """Build position detail message"""
    emoji = pnl_emoji(pos.pnl_usd)
    lines = [
        f"📍 {pos.pair_name} [{pos.position_type}]",
        f"   💰 {format_usd(pos.total_value_usd)}",
        f"   {emoji} PnL: {format_usd(pos.pnl_usd)} ({format_pct(pos.pnl_pct)})",
        f"   💸 Fee: {format_usd(pos.unclaimed_fees_usd)}",
    ]
    
    if pos.position_type == "DLMM":
        range_status = "✅ In Range" if pos.in_range else "⛔ Out of Range"
        lines.append(f"   🎯 {range_status}")
        if pos.in_range:
            lines.append(f"      {pos.bins_to_lower}↓ / {pos.bins_to_upper}↑ bins")
    
    return "\n".join(lines)


def build_info_message(snapshot: PortfolioSnapshot) -> str:
    """Build /info command response"""
    emoji = pnl_emoji(snapshot.total_pnl_usd)
    
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━",
        "📊 PORTFOLIO INFO",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💰 Balance:  {format_usd(snapshot.total_value_usd)}",
        f"             {format_idr(snapshot.total_value_usd)}",
        f"{emoji} PnL:      {format_usd(snapshot.total_pnl_usd)} ({format_pct(snapshot.total_pnl_pct)})",
        f"             {format_idr(snapshot.total_pnl_usd)}",
        f"💸 Fees:     {format_usd(snapshot.total_fees_usd)}",
        "",
        f"📍 Positions: {len(snapshot.positions)}",
        f"   • DLMM: {snapshot.dlmm_count}",
        f"   • DAMM: {snapshot.damm_count}",
        "",
        f"🕐 Updated: {snapshot.timestamp.strftime('%H:%M:%S UTC')}",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]
    
    return "\n".join(lines)


def build_status_message(snapshot: PortfolioSnapshot) -> str:
    """Build /status command response"""
    if not snapshot.positions:
        return "📭 Tidak ada posisi aktif"
    
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━",
        "📋 POSITION STATUS",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    
    for pos in snapshot.positions[:10]:
        emoji = pnl_emoji(pos.pnl_usd)
        lines.append(f"• {pos.pair_name}")
        lines.append(f"  PnL {format_usd(pos.pnl_usd)}  |  Fee {format_usd(pos.unclaimed_fees_usd)}")
        lines.append("")
    
    if len(snapshot.positions) > 10:
        lines.append(f"... +{len(snapshot.positions)-10} posisi lainnya")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


def build_range_message(snapshot: PortfolioSnapshot) -> str:
    """Build /range command response"""
    dlmm_positions = [p for p in snapshot.positions if p.position_type == "DLMM"]
    
    if not dlmm_positions:
        return "📭 Tidak ada posisi DLMM"
    
    lines = [
        "━━━━━━━━━━━━━━━━━━━━━",
        "🎯 RANGE STATUS",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    
    for pos in dlmm_positions:
        if not pos.in_range:
            lines.append(f"⛔ {pos.pair_name} — keluar dari range")
        elif pos.bins_to_lower <= 3:
            lines.append(f"⚠️ {pos.pair_name} — dekat batas bawah ({pos.bins_to_lower} bin)")
        elif pos.bins_to_upper <= 3:
            lines.append(f"⚠️ {pos.pair_name} — dekat batas atas ({pos.bins_to_upper} bin)")
        else:
            lines.append(f"✅ {pos.pair_name} — aman ({pos.bins_to_lower}↓ / {pos.bins_to_upper}↑ bin)")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BOT CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class MeteoraBot:
    """Main bot orchestrator"""
    
    def __init__(self):
        self.api = MeteoraAPI(WALLET_ADDRESS)
        self.telegram = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DRY_RUN)
        self.last_snapshot: Optional[PortfolioSnapshot] = None
    
    def run_once(self, notify: bool = True) -> PortfolioSnapshot:
        """Run single check cycle"""
        logger.info("Fetching portfolio...")
        snapshot = self.api.fetch_portfolio()
        
        logger.info(f"Portfolio: {format_usd(snapshot.total_value_usd)} | "
                   f"PnL: {format_usd(snapshot.total_pnl_usd)} | "
                   f"Positions: {len(snapshot.positions)}")
        
        if notify:
            msg = build_summary_message(snapshot)
            self.telegram.send_message(msg)
        
        self.last_snapshot = snapshot
        return snapshot
    
    def handle_command(self, command: str) -> str:
        """Handle Telegram command"""
        snapshot = self.api.fetch_portfolio()
        
        if command == "/info":
            return build_info_message(snapshot)
        elif command == "/status":
            return build_status_message(snapshot)
        elif command == "/range":
            return build_range_message(snapshot)
        elif command == "/help":
            return self._help_message()
        else:
            return f"❓ Unknown command: {command}\nUse /help for available commands"
    
    def _help_message(self) -> str:
        return "\n".join([
            "━━━━━━━━━━━━━━━━━━━━━",
            "📚 AVAILABLE COMMANDS",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
            "/info   — Portfolio summary",
            "/status — Position details",
            "/range  — DLMM range status",
            "/help   — This message",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
        ])
    
    def run_loop(self):
        """Run continuous monitoring loop"""
        logger.info(f"Starting monitor loop (interval: {POLL_INTERVAL}s)")
        
        while True:
            try:
                self.run_once(notify=True)
            except KeyboardInterrupt:
                logger.info("Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in loop: {e}")
            
            logger.info(f"Sleeping for {POLL_INTERVAL}s...")
            time.sleep(POLL_INTERVAL)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Meteora Portfolio Monitor Bot")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Don't send Telegram messages")
    parser.add_argument("--notify-on-bootstrap", action="store_true", help="Send notification on startup")
    parser.add_argument("--command", type=str, help="Handle a specific command")
    args = parser.parse_args()
    
    # Override dry run if specified
    global DRY_RUN
    if args.dry_run:
        DRY_RUN = True
    
    # Validate config
    if not WALLET_ADDRESS:
        logger.error("WALLET_ADDRESS not set in environment")
        sys.exit(1)
    
    logger.info(f"Wallet: {WALLET_ADDRESS[:8]}...{WALLET_ADDRESS[-4:]}")
    logger.info(f"Dry run: {DRY_RUN}")
    
    bot = MeteoraBot()
    
    if args.command:
        response = bot.handle_command(args.command)
        print(response)
    elif args.once:
        bot.run_once(notify=args.notify_on_bootstrap)
    else:
        bot.run_loop()


if __name__ == "__main__":
    main()
