"""
Telegram Bot Integration for Trading Bot
Provides remote control and monitoring via Telegram
"""
import asyncio
import io
import csv
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from loguru import logger
import json

from utils.storage_manager import get_storage


def format_pnl(value: float) -> str:
    """Format P&L with sign and emoji."""
    if value >= 0:
        return f"+${value:.2f} ✅"
    else:
        return f"-${abs(value):.2f} 🔻"


def format_duration(seconds: int) -> str:
    """Format duration in human-readable form."""
    if seconds < 3600:
        return f"{seconds // 60}m"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


class TelegramBot:
    """
    Telegram bot for remote trading bot control and monitoring

    Features:
    - Real-time notifications for trades
    - Position tracking
    - P&L reporting (daily/weekly/monthly/all-time)
    - Bot control (start/stop/emergency)
    - Status updates
    """

    def __init__(self, token: str, authorized_users: List[int], trading_bot=None):
        """
        Initialize Telegram bot

        Args:
            token: Telegram bot token
            authorized_users: List of authorized user IDs
            trading_bot: Reference to main trading bot
        """
        self.token = token
        self.authorized_users = set(authorized_users)
        self.trading_bot = trading_bot
        self.app = None

        # Track statistics
        self.start_time = datetime.now()
        self.notifications_sent = 0
        self.commands_executed = 0

        logger.info(f"Telegram bot initialized with {len(authorized_users)} authorized users")

    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in self.authorized_users

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id

        if not self.is_authorized(user_id):
            await update.message.reply_text(
                "⛔ Unauthorized access. Your user ID has been logged."
            )
            logger.warning(f"Unauthorized access attempt from user {user_id}")
            return

        welcome_message = (
            "🤖 **Binance Trading Bot Control Panel**\n\n"
            "Welcome! You can now control and monitor your trading bot.\n\n"
            "**Key Commands:**\n"
            "/status - Bot status and summary\n"
            "/pnl - Today's P&L\n"
            "/trades - Recent trade history\n"
            "/stats - Lifetime statistics\n"
            "/help - Show all commands\n\n"
            "📊 Real-time trade notifications enabled!"
        )

        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        self.commands_executed += 1

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            if not self.trading_bot:
                await update.message.reply_text("⚠️ Trading bot not connected")
                return

            # Sync balance from exchange (live mode only)
            from config import Config
            if Config.TRADING_MODE == 'live':
                self.trading_bot.risk_manager.sync_balance_from_exchange(self.trading_bot.client)

            # Get portfolio summary
            summary = self.trading_bot.risk_manager.get_portfolio_summary()

            status_emoji = "✅" if self.trading_bot.is_running else "⏸️"
            status_text = "RUNNING" if self.trading_bot.is_running else "STOPPED"
            mode_emoji = "🔴" if Config.TRADING_MODE == 'live' else "📄"
            mode_text = "LIVE" if Config.TRADING_MODE == 'live' else "PAPER"

            runtime = datetime.now() - self.trading_bot.start_time if self.trading_bot.start_time else timedelta(0)
            hours = int(runtime.total_seconds() // 3600)
            minutes = int((runtime.total_seconds() % 3600) // 60)

            message = (
                f"{status_emoji} **BOT STATUS: {status_text}** {mode_emoji} **{mode_text}**\n\n"
                f"**Account Summary:**\n"
                f"💰 Balance: ${summary['balance']:,.2f}\n"
                f"📈 Total P&L: ${summary['total_pnl']:,.2f} ({summary['total_pnl_pct']:+.2f}%)\n"
                f"📊 Daily P&L: ${summary['daily_pnl']:,.2f}\n\n"
                f"**Risk Metrics:**\n"
                f"🔥 Portfolio Heat: {summary['portfolio_heat']:.1%}\n"
                f"📍 Open Positions: {summary['open_positions']}\n"
                f"⏱️ Runtime: {hours}h {minutes}m\n\n"
                f"**Performance:**\n"
                f"✅ Winning Trades: {summary['winning_trades']}\n"
                f"❌ Losing Trades: {summary['losing_trades']}\n"
                f"📊 Win Rate: {summary['win_rate']:.1f}%\n"
                f"🎯 Total Trades: {summary['total_trades']}"
            )

            # Add daily target progress
            from config import Config
            profit_progress = (summary['daily_pnl'] / Config.TARGET_DAILY_PROFIT) * 100
            loss_progress = abs(summary['daily_pnl'] / Config.MAX_DAILY_LOSS) * 100 if summary['daily_pnl'] < 0 else 0

            message += f"\n\n**Daily Targets:**\n"
            message += f"🎯 Profit: ${summary['daily_pnl']:.2f} / ${Config.TARGET_DAILY_PROFIT:.2f} ({profit_progress:.0f}%)\n"
            message += f"🛡️ Loss Limit: {loss_progress:.0f}% used"

            await update.message.reply_text(message, parse_mode='Markdown')
            self.commands_executed += 1

        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text(f"❌ Error getting status: {str(e)}")

    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /positions command"""
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            if not self.trading_bot:
                await update.message.reply_text("⚠️ Trading bot not connected")
                return

            positions = self.trading_bot.risk_manager.get_all_positions()

            if not positions:
                await update.message.reply_text("📭 No open positions")
                return

            message = "📊 **OPEN POSITIONS**\n\n"

            for i, pos in enumerate(positions, 1):
                pnl_emoji = "🟢" if pos.unrealized_pnl > 0 else "🔴" if pos.unrealized_pnl < 0 else "⚪"

                message += (
                    f"**{i}. {pos.symbol}**\n"
                    f"Entry: ${pos.entry_price:,.2f}\n"
                    f"Current: ${pos.current_price:,.2f}\n"
                    f"Size: {pos.quantity:.6f}\n"
                    f"{pnl_emoji} P&L: ${pos.unrealized_pnl:,.2f} ({pos.unrealized_pnl_pct:+.2f}%)\n"
                    f"Stop: ${pos.stop_loss:,.2f}\n"
                    f"Target: ${pos.take_profit:,.2f}\n\n"
                )

            # Add total unrealized P&L
            total_unrealized = sum(p.unrealized_pnl for p in positions)
            message += f"**Total Unrealized P&L:** ${total_unrealized:,.2f}"

            await update.message.reply_text(message, parse_mode='Markdown')
            self.commands_executed += 1

        except Exception as e:
            logger.error(f"Error in positions command: {e}")
            await update.message.reply_text(f"❌ Error getting positions: {str(e)}")

    async def pnl_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Handle /pnl command with optional period argument.

        Usage:
            /pnl          - Today's P&L (or show period buttons)
            /pnl daily    - Today's P&L
            /pnl weekly   - This week (Mon-Sun)
            /pnl monthly  - This calendar month
            /pnl all      - All-time statistics
        """
        if not self.is_authorized(update.effective_user.id):
            return

        args = context.args
        storage = get_storage()
        today = datetime.now(timezone.utc)

        # If no arguments, show today's P&L directly (most useful default)
        if not args:
            await self._show_daily_pnl(update, storage, today)
            self.commands_executed += 1
            return

        period = args[0].lower()

        if period == 'daily':
            await self._show_daily_pnl(update, storage, today)

        elif period == 'weekly':
            # This week (Monday to today)
            start_of_week = today - timedelta(days=today.weekday())
            stats = storage.get_stats_for_period(
                start_of_week.strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d")
            )

            if stats['total_trades'] == 0:
                message = (
                    f"📊 **THIS WEEK'S PERFORMANCE**\n"
                    f"({start_of_week.strftime('%d %b')} - {today.strftime('%d %b %Y')})\n\n"
                    f"No trades this week yet."
                )
            else:
                message = (
                    f"📊 **THIS WEEK'S PERFORMANCE**\n"
                    f"({start_of_week.strftime('%d %b')} - {today.strftime('%d %b %Y')})\n\n"
                    f"💰 Total P&L: {format_pnl(stats['realised_pnl'])}\n"
                    f"📊 Trades: {stats['total_trades']} "
                    f"({stats['wins']}W / {stats['losses']}L)\n"
                    f"📈 Win Rate: {stats['win_rate']}%\n"
                    f"📅 Trading Days: {stats['days_count']}"
                )

            await update.message.reply_text(message, parse_mode='Markdown')

        elif period == 'monthly':
            # This calendar month
            start_of_month = today.replace(day=1)
            stats = storage.get_stats_for_period(
                start_of_month.strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d")
            )

            if stats['total_trades'] == 0:
                message = (
                    f"📊 **THIS MONTH'S PERFORMANCE**\n"
                    f"({today.strftime('%B %Y')})\n\n"
                    f"No trades this month yet."
                )
            else:
                message = (
                    f"📊 **THIS MONTH'S PERFORMANCE**\n"
                    f"({today.strftime('%B %Y')})\n\n"
                    f"💰 Total P&L: {format_pnl(stats['realised_pnl'])}\n"
                    f"📊 Trades: {stats['total_trades']} "
                    f"({stats['wins']}W / {stats['losses']}L)\n"
                    f"📈 Win Rate: {stats['win_rate']}%\n"
                    f"📅 Trading Days: {stats['days_count']}"
                )

            await update.message.reply_text(message, parse_mode='Markdown')

        elif period == 'all' or period == 'alltime':
            # All-time statistics from persistent storage
            stats = storage.get_lifetime_stats()

            if stats.get('total_trades', 0) == 0:
                message = (
                    "🏆 **ALL-TIME PERFORMANCE**\n\n"
                    "No trade history yet.\n"
                    "Statistics will appear after your first completed trade."
                )
            else:
                message = (
                    f"🏆 **ALL-TIME PERFORMANCE**\n\n"
                    f"📅 Period: {stats.get('first_trade_date', 'N/A')} → {stats.get('last_trade_date', 'N/A')}\n"
                    f"📆 Trading Days: {stats.get('total_days_trading', 0)}\n"
                    f"{'─' * 25}\n"
                    f"💰 Total P&L: {format_pnl(stats.get('total_pnl', 0))}\n"
                    f"📈 Daily Average: {format_pnl(stats.get('average_daily_pnl', 0))}\n\n"
                    f"📊 Total Trades: {stats.get('total_trades', 0)}\n"
                    f"✅ Winners: {stats.get('total_wins', 0)} ({stats.get('win_rate', 0)}%)\n"
                    f"❌ Losers: {stats.get('total_losses', 0)}\n\n"
                    f"📈 Avg Win: +${stats.get('average_win', 0):.2f}\n"
                    f"📉 Avg Loss: -${abs(stats.get('average_loss', 0)):.2f}\n"
                    f"⚖️ Profit Factor: {stats.get('profit_factor', 0)}"
                )

                # Add best/worst day
                if stats.get('best_day'):
                    message += f"\n\n🏆 Best Day: +${stats['best_day']['pnl']:.2f} ({stats['best_day']['date']})"
                if stats.get('worst_day') and stats['worst_day']['pnl'] < 0:
                    message += f"\n😔 Worst Day: -${abs(stats['worst_day']['pnl']):.2f} ({stats['worst_day']['date']})"

                # Add current streak
                streak = stats.get('current_streak', {})
                if streak.get('count', 0) >= 2:
                    emoji = "🔥" if streak['type'] == "win" else "❄️"
                    message += f"\n\nCurrent Streak: {emoji} {streak['count']} {streak['type']}s"

            await update.message.reply_text(message, parse_mode='Markdown')

        else:
            await update.message.reply_text(
                "❓ Unknown period. Use:\n"
                "/pnl - Today\n"
                "/pnl daily - Today\n"
                "/pnl weekly - This week\n"
                "/pnl monthly - This month\n"
                "/pnl all - All time"
            )

        self.commands_executed += 1

    async def _show_daily_pnl(self, update: Update, storage, today: datetime):
        """Show today's P&L from persistent storage."""
        today_str = today.strftime("%Y-%m-%d")
        stats = storage.get_daily_stats(today_str)

        # Also get unrealized P&L from open positions if available
        unrealized_pnl = 0
        open_positions = 0
        if self.trading_bot:
            positions = self.trading_bot.risk_manager.get_all_positions()
            unrealized_pnl = sum(p.unrealized_pnl for p in positions)
            open_positions = len(positions)

        if not stats or stats.get('total_trades', 0) == 0:
            message = (
                f"📊 **TODAY'S PERFORMANCE** ({today.strftime('%d %b %Y')})\n\n"
                f"No completed trades today yet.\n"
            )
            if open_positions > 0:
                message += f"\n📍 Open Positions: {open_positions}\n"
                message += f"📈 Unrealized P&L: {format_pnl(unrealized_pnl)}"
        else:
            realised = stats.get('realised_pnl', 0)
            total_pnl = realised + unrealized_pnl

            message = (
                f"📊 **TODAY'S PERFORMANCE** ({today.strftime('%d %b %Y')})\n\n"
                f"💰 Realised P&L: {format_pnl(realised)}\n"
            )
            if open_positions > 0:
                message += f"📈 Unrealised P&L: {format_pnl(unrealized_pnl)} ({open_positions} open)\n"
                message += f"{'─' * 25}\n"
                message += f"📊 Net P&L: {format_pnl(total_pnl)}\n\n"
            else:
                message += "\n"

            message += (
                f"📊 Trades: {stats['total_trades']} "
                f"({stats['wins']}W / {stats['losses']}L)\n"
                f"📈 Win Rate: {stats['win_rate']}%\n"
            )

            if stats.get('best_trade_pair'):
                message += f"\n🏆 Best: {stats['best_trade_pair']} +${stats['best_trade_pnl']:.2f}"
            if stats.get('worst_trade_pair') and stats.get('worst_trade_pnl', 0) < 0:
                message += f"\n😔 Worst: {stats['worst_trade_pair']} -${abs(stats['worst_trade_pnl']):.2f}"

            # Add streak info from lifetime stats
            lifetime = storage.get_lifetime_stats()
            streak = lifetime.get('current_streak', {})
            if streak.get('count', 0) >= 3:
                emoji = "🔥" if streak['type'] == "win" else "❄️"
                message += f"\n\nStreak: {emoji} {streak['count']} {streak['type']}s in a row!"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def pnl_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle P&L button callbacks (legacy support)"""
        query = update.callback_query
        await query.answer()

        if not self.is_authorized(query.from_user.id):
            return

        try:
            period = query.data.replace('pnl_', '')
            storage = get_storage()
            today = datetime.now(timezone.utc)

            if period == 'daily':
                today_str = today.strftime("%Y-%m-%d")
                stats = storage.get_daily_stats(today_str)

                if not stats or stats.get('total_trades', 0) == 0:
                    message = f"📅 **DAILY P&L** ({today.strftime('%d %b')})\n\nNo trades today yet."
                else:
                    message = (
                        f"📅 **DAILY P&L** ({today.strftime('%d %b')})\n\n"
                        f"💰 P&L: {format_pnl(stats['realised_pnl'])}\n"
                        f"📊 Trades: {stats['total_trades']} ({stats['wins']}W/{stats['losses']}L)\n"
                        f"📈 Win Rate: {stats['win_rate']}%"
                    )

            elif period == 'weekly':
                start_of_week = today - timedelta(days=today.weekday())
                stats = storage.get_stats_for_period(
                    start_of_week.strftime("%Y-%m-%d"),
                    today.strftime("%Y-%m-%d")
                )
                message = (
                    f"📊 **WEEKLY P&L**\n\n"
                    f"💰 P&L: {format_pnl(stats['realised_pnl'])}\n"
                    f"📊 Trades: {stats['total_trades']} ({stats['wins']}W/{stats['losses']}L)\n"
                    f"📈 Win Rate: {stats['win_rate']}%"
                )

            elif period == 'monthly':
                start_of_month = today.replace(day=1)
                stats = storage.get_stats_for_period(
                    start_of_month.strftime("%Y-%m-%d"),
                    today.strftime("%Y-%m-%d")
                )
                message = (
                    f"📈 **MONTHLY P&L**\n\n"
                    f"💰 P&L: {format_pnl(stats['realised_pnl'])}\n"
                    f"📊 Trades: {stats['total_trades']} ({stats['wins']}W/{stats['losses']}L)\n"
                    f"📈 Win Rate: {stats['win_rate']}%"
                )

            elif period == 'alltime':
                stats = storage.get_lifetime_stats()
                if stats.get('total_trades', 0) == 0:
                    message = "🏆 **ALL-TIME P&L**\n\nNo trade history yet."
                else:
                    message = (
                        f"🏆 **ALL-TIME P&L**\n\n"
                        f"💰 Total P&L: {format_pnl(stats.get('total_pnl', 0))}\n"
                        f"📊 Trades: {stats.get('total_trades', 0)} "
                        f"({stats.get('total_wins', 0)}W/{stats.get('total_losses', 0)}L)\n"
                        f"📈 Win Rate: {stats.get('win_rate', 0)}%\n"
                        f"⚖️ Profit Factor: {stats.get('profit_factor', 0)}"
                    )
            else:
                message = "Unknown period"

            await query.edit_message_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in P&L callback: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def trades_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Show recent trade history.

        Usage:
            /trades      - Last 10 trades
            /trades 25   - Last 25 trades
            /trades today - Today's trades only
        """
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            storage = get_storage()
            args = context.args

            if args and args[0].lower() == "today":
                trades = storage.get_trades_for_day(
                    datetime.now(timezone.utc).strftime("%Y-%m-%d")
                )
                title = "TODAY'S TRADES"
            else:
                limit = int(args[0]) if args and args[0].isdigit() else 10
                limit = min(limit, 50)  # Cap at 50
                trades = storage.get_trades(limit=limit)
                title = f"LAST {len(trades)} TRADES"

            if not trades:
                await update.message.reply_text("📜 No trade history found.")
                return

            message = f"📜 **{title}**\n\n"

            for trade in trades:
                emoji = "✅" if trade.get('is_win', False) else "❌"
                pnl = trade.get('net_pnl_usdt', trade.get('pnl_usdt', 0))
                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                duration = format_duration(trade.get('duration_seconds', 0))
                pnl_pct = trade.get('pnl_percent', 0)

                message += (
                    f"{emoji} {trade.get('pair', '?')} | {pnl_str} ({pnl_pct:+.1f}%) | {duration}\n"
                )

            # Summary
            wins = sum(1 for t in trades if t.get('is_win', False))
            total_pnl = sum(t.get('net_pnl_usdt', 0) for t in trades)

            message += (
                f"\n{'─' * 30}\n"
                f"**Summary:** {wins}W/{len(trades)-wins}L | "
                f"Total: {format_pnl(total_pnl)}"
            )

            await update.message.reply_text(message, parse_mode='Markdown')
            self.commands_executed += 1

        except Exception as e:
            logger.error(f"Error in trades command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def winners_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show last 10 winning trades."""
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            storage = get_storage()
            trades = storage.get_winning_trades(limit=10)

            if not trades:
                await update.message.reply_text("🏆 No winning trades yet! Keep at it! 💪")
                return

            message = "🏆 **LAST 10 WINNERS**\n\n"

            for trade in trades:
                pnl = trade.get('net_pnl_usdt', 0)
                pnl_pct = trade.get('pnl_percent', 0)
                date = trade.get('exit_time', '')[:10]
                duration = format_duration(trade.get('duration_seconds', 0))

                message += (
                    f"✅ {trade.get('pair', '?')} | +${pnl:.2f} (+{pnl_pct:.1f}%) | {duration} | {date}\n"
                )

            avg_win = sum(t.get('net_pnl_usdt', 0) for t in trades) / len(trades)
            message += f"\n**Average Win:** +${avg_win:.2f}"

            await update.message.reply_text(message, parse_mode='Markdown')
            self.commands_executed += 1

        except Exception as e:
            logger.error(f"Error in winners command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def losers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show last 10 losing trades."""
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            storage = get_storage()
            trades = storage.get_losing_trades(limit=10)

            if not trades:
                await update.message.reply_text("🎉 No losing trades! Perfect record! 🚀")
                return

            message = "📉 **LAST 10 LOSSES**\n\n"

            for trade in trades:
                pnl = trade.get('net_pnl_usdt', 0)
                pnl_pct = trade.get('pnl_percent', 0)
                date = trade.get('exit_time', '')[:10]
                reason = trade.get('exit_reason', 'unknown').replace('_', ' ').title()

                message += (
                    f"❌ {trade.get('pair', '?')} | -${abs(pnl):.2f} ({pnl_pct:.1f}%) | {reason} | {date}\n"
                )

            avg_loss = sum(t.get('net_pnl_usdt', 0) for t in trades) / len(trades)
            message += f"\n**Average Loss:** -${abs(avg_loss):.2f}"

            await update.message.reply_text(message, parse_mode='Markdown')
            self.commands_executed += 1

        except Exception as e:
            logger.error(f"Error in losers command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show comprehensive lifetime statistics."""
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            storage = get_storage()
            stats = storage.get_lifetime_stats()

            if stats.get('total_trades', 0) == 0:
                await update.message.reply_text(
                    "📈 **LIFETIME STATISTICS**\n\n"
                    "No trade history yet.\n"
                    "Complete your first trade to see statistics."
                )
                return

            message = (
                f"📈 **LIFETIME STATISTICS**\n\n"
                f"**📅 Period**\n"
                f"{stats.get('first_trade_date', 'N/A')} → {stats.get('last_trade_date', 'N/A')}\n"
                f"Trading days: {stats.get('total_days_trading', 0)}\n\n"
                f"**💰 Performance**\n"
                f"Total P&L: {format_pnl(stats.get('total_pnl', 0))}\n"
                f"Daily Avg: {format_pnl(stats.get('average_daily_pnl', 0))}\n"
                f"Profit Factor: {stats.get('profit_factor', 0)}\n\n"
                f"**📊 Trade Stats**\n"
                f"Total: {stats.get('total_trades', 0)} "
                f"({stats.get('total_wins', 0)}W / {stats.get('total_losses', 0)}L)\n"
                f"Win Rate: {stats.get('win_rate', 0)}%\n"
                f"Avg Win: +${stats.get('average_win', 0):.2f}\n"
                f"Avg Loss: -${abs(stats.get('average_loss', 0)):.2f}\n\n"
                f"**🏆 Records**\n"
            )

            if stats.get('largest_win'):
                message += (
                    f"Best Trade: +${stats['largest_win']['pnl']:.2f} "
                    f"({stats['largest_win']['pair']})\n"
                )
            if stats.get('largest_loss') and stats['largest_loss']['pnl'] < 0:
                message += (
                    f"Worst Trade: -${abs(stats['largest_loss']['pnl']):.2f} "
                    f"({stats['largest_loss']['pair']})\n"
                )
            if stats.get('best_day'):
                message += f"Best Day: +${stats['best_day']['pnl']:.2f} ({stats['best_day']['date']})\n"
            if stats.get('worst_day') and stats['worst_day']['pnl'] < 0:
                message += f"Worst Day: -${abs(stats['worst_day']['pnl']):.2f} ({stats['worst_day']['date']})\n"

            message += f"Best Win Streak: {stats.get('best_win_streak', 0)}\n"

            # Current streak
            streak = stats.get('current_streak', {})
            if streak.get('count', 0) >= 2:
                emoji = "🔥" if streak['type'] == "win" else "❄️"
                message += f"\nCurrent: {emoji} {streak['count']} {streak['type']}s"

            await update.message.reply_text(message, parse_mode='Markdown')
            self.commands_executed += 1

        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def export_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Export trade history as CSV file."""
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            storage = get_storage()
            trades = storage.get_trades()

            if not trades:
                await update.message.reply_text("📊 No trade history to export.")
                return

            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow([
                'ID', 'Pair', 'Side', 'Entry Price', 'Exit Price',
                'Size', 'P&L ($)', 'P&L (%)', 'Fees', 'Net P&L',
                'Entry Time', 'Exit Time', 'Duration', 'Exit Reason', 'Win'
            ])

            # Data
            for trade in trades:
                duration_mins = trade.get('duration_seconds', 0) // 60
                writer.writerow([
                    trade.get('id', ''),
                    trade.get('pair', ''),
                    trade.get('side', ''),
                    trade.get('entry_price', 0),
                    trade.get('exit_price', 0),
                    trade.get('size', 0),
                    trade.get('pnl_usdt', 0),
                    trade.get('pnl_percent', 0),
                    trade.get('fees_usdt', 0),
                    trade.get('net_pnl_usdt', 0),
                    trade.get('entry_time', ''),
                    trade.get('exit_time', ''),
                    f"{duration_mins}m",
                    trade.get('exit_reason', ''),
                    'Yes' if trade.get('is_win') else 'No'
                ])

            # Send file
            output.seek(0)
            filename = f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            await update.message.reply_document(
                document=io.BytesIO(output.getvalue().encode()),
                filename=filename,
                caption=f"📊 Exported {len(trades)} trades"
            )
            self.commands_executed += 1

        except Exception as e:
            logger.error(f"Error in export command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command"""
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            if not self.trading_bot:
                await update.message.reply_text("⚠️ Trading bot not connected")
                return

            balances = self.trading_bot.client.get_account_balance()
            summary = self.trading_bot.risk_manager.get_portfolio_summary()

            message = "💰 **ACCOUNT BALANCE**\n\n"

            # USDT balance
            if 'USDT' in balances:
                usdt = balances['USDT']
                message += (
                    f"**USDT:**\n"
                    f"Free: ${usdt['free']:,.2f}\n"
                    f"Locked: ${usdt['locked']:,.2f}\n"
                    f"Total: ${usdt['total']:,.2f}\n\n"
                )

            # Other significant balances
            message += "**Other Assets:**\n"
            count = 0
            for asset, bal in balances.items():
                if asset != 'USDT' and bal['total'] > 0.001:
                    message += f"{asset}: {bal['total']:.8f}\n"
                    count += 1
                    if count >= 10:
                        break

            message += (
                f"\n**Portfolio:**\n"
                f"Total Value: ${summary['portfolio_value']:,.2f}\n"
                f"Unrealized P&L: ${summary['unrealized_pnl']:,.2f}"
            )

            await update.message.reply_text(message, parse_mode='Markdown')
            self.commands_executed += 1

        except Exception as e:
            logger.error(f"Error in balance command: {e}")
            await update.message.reply_text(f"❌ Error getting balance: {str(e)}")

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command - graceful stop"""
        if not self.is_authorized(update.effective_user.id):
            return

        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Stop", callback_data='stop_confirm'),
                InlineKeyboardButton("❌ Cancel", callback_data='stop_cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⚠️ **STOP TRADING BOT?**\n\n"
            "This will:\n"
            "• Stop opening new positions\n"
            "• Keep existing positions open\n"
            "• Continue monitoring for exits\n\n"
            "Confirm?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resume command"""
        if not self.is_authorized(update.effective_user.id):
            return

        try:
            if self.trading_bot and not self.trading_bot.is_running:
                self.trading_bot.is_running = True
                await update.message.reply_text("✅ **Bot resumed!** Trading will continue.")
                await self.send_notification("🟢 **Bot Resumed**\nTrading operations continuing.")
            else:
                await update.message.reply_text("ℹ️ Bot is already running")

        except Exception as e:
            logger.error(f"Error in resume command: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def emergency_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /emergency command - close all and stop"""
        if not self.is_authorized(update.effective_user.id):
            return

        keyboard = [
            [
                InlineKeyboardButton("🚨 CONFIRM EMERGENCY STOP", callback_data='emergency_confirm'),
            ],
            [
                InlineKeyboardButton("❌ Cancel", callback_data='emergency_cancel')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🚨 **EMERGENCY STOP**\n\n"
            "⚠️ WARNING: This will:\n"
            "• Close ALL open positions immediately\n"
            "• Stop the trading bot\n"
            "• Exit at market prices\n\n"
            "**Use only in emergencies!**\n\n"
            "Are you absolutely sure?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    async def emergency_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle emergency stop confirmation"""
        query = update.callback_query
        await query.answer()

        if not self.is_authorized(query.from_user.id):
            return

        if query.data == 'emergency_confirm':
            try:
                await query.edit_message_text("🚨 **EMERGENCY STOP ACTIVATED**\n\nClosing all positions...")

                if self.trading_bot:
                    # Close all positions
                    positions = self.trading_bot.risk_manager.get_all_positions()
                    closed_count = 0

                    for pos in positions:
                        current_price = self.trading_bot.client.get_symbol_price(pos.symbol)
                        if current_price:
                            await self.trading_bot._close_position(pos.symbol, current_price, "Emergency stop")
                            closed_count += 1

                    # Stop bot
                    self.trading_bot.is_running = False

                    await self.send_notification(
                        f"🚨 **EMERGENCY STOP COMPLETE**\n\n"
                        f"Closed {closed_count} positions\n"
                        f"Bot stopped"
                    )
                else:
                    await query.edit_message_text("⚠️ Trading bot not connected")

            except Exception as e:
                logger.error(f"Error in emergency stop: {e}")
                await query.edit_message_text(f"❌ Error: {str(e)}")

        elif query.data == 'emergency_cancel':
            await query.edit_message_text("✅ Emergency stop cancelled")

    async def stop_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle stop confirmation"""
        query = update.callback_query
        await query.answer()

        if not self.is_authorized(query.from_user.id):
            return

        if query.data == 'stop_confirm':
            try:
                if self.trading_bot:
                    self.trading_bot.is_running = False
                    positions = len(self.trading_bot.risk_manager.get_all_positions())

                    await query.edit_message_text(
                        f"✅ **Bot Stopped**\n\n"
                        f"• New positions: Disabled\n"
                        f"• Open positions: {positions} (still monitored)\n"
                        f"• Status: PAUSED\n\n"
                        f"Use /resume to restart trading"
                    )
                    await self.send_notification("⏸️ **Bot Stopped**\nNo new positions will be opened.")
                else:
                    await query.edit_message_text("⚠️ Trading bot not connected")

            except Exception as e:
                logger.error(f"Error in stop: {e}")
                await query.edit_message_text(f"❌ Error: {str(e)}")

        elif query.data == 'stop_cancel':
            await query.edit_message_text("✅ Stop cancelled - bot still running")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        if not self.is_authorized(update.effective_user.id):
            return

        help_text = (
            "🤖 **TRADING BOT COMMANDS**\n\n"
            "**📊 Monitoring:**\n"
            "/status - Bot status and summary\n"
            "/positions - View open positions\n"
            "/balance - Account balance\n\n"
            "**💰 Performance:**\n"
            "/pnl - Today's P&L\n"
            "/pnl weekly - This week's P&L\n"
            "/pnl monthly - This month's P&L\n"
            "/pnl all - All-time performance\n"
            "/trades - Recent trade history\n"
            "/winners - Last 10 winning trades\n"
            "/losers - Last 10 losing trades\n"
            "/stats - Comprehensive statistics\n"
            "/export - Download trades as CSV\n\n"
            "**🎮 Control:**\n"
            "/stop - Stop trading (keep positions)\n"
            "/resume - Resume trading\n"
            "/emergency - ⚠️ Close ALL positions\n\n"
            "**ℹ️ Help:**\n"
            "/help - Show this message\n\n"
            "**🔔 Notifications:**\n"
            "Automatic alerts for trades, targets, and errors.\n\n"
            f"Your ID: `{update.effective_user.id}`"
        )

        await update.message.reply_text(help_text, parse_mode='Markdown')
        self.commands_executed += 1

    async def send_notification(self, message: str):
        """
        Send notification to all authorized users

        Args:
            message: Notification message
        """
        try:
            if not self.app:
                logger.warning("Telegram notification skipped - bot not initialized (self.app is None)")
                return

            logger.debug(f"Sending Telegram notification to {len(self.authorized_users)} users")
            for user_id in self.authorized_users:
                try:
                    await self.app.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    self.notifications_sent += 1
                    logger.info(f"Telegram notification sent to user {user_id}")
                except Exception as e:
                    logger.error(f"Failed to send notification to {user_id}: {e}")

        except Exception as e:
            logger.error(f"Error sending notifications: {e}")

    async def notify_trade_opened(self, symbol: str, side: str, entry_price: float,
                                 size: float, stop_loss: float, take_profit: float, strategy: str):
        """Notify when trade is opened"""
        message = (
            f"🟢 **TRADE OPENED**\n\n"
            f"Symbol: {symbol}\n"
            f"Side: {side}\n"
            f"Strategy: {strategy}\n"
            f"Entry: ${entry_price:,.2f}\n"
            f"Size: {size:.6f}\n"
            f"Stop Loss: ${stop_loss:,.2f}\n"
            f"Exit: 5% Trailing Stop 📈\n"
            f"Risk: ${abs(entry_price - stop_loss) * size:,.2f}"
        )
        await self.send_notification(message)

    async def notify_trade_closed(self, symbol: str, entry_price: float, exit_price: float,
                                 pnl: float, pnl_pct: float, reason: str):
        """Notify when trade is closed"""
        emoji = "🎉" if pnl > 0 else "😔"
        message = (
            f"{emoji} **TRADE CLOSED**\n\n"
            f"Symbol: {symbol}\n"
            f"Reason: {reason}\n"
            f"Entry: ${entry_price:,.2f}\n"
            f"Exit: ${exit_price:,.2f}\n"
            f"P&L: ${pnl:,.2f} ({pnl_pct:+.2f}%)"
        )
        await self.send_notification(message)

    async def notify_daily_target_met(self, daily_pnl: float):
        """Notify when daily profit target is met"""
        message = (
            f"🎯 **DAILY TARGET ACHIEVED!**\n\n"
            f"Today's Profit: ${daily_pnl:,.2f}\n\n"
            f"Excellent work! 🚀"
        )
        await self.send_notification(message)

    async def notify_daily_loss_limit(self, daily_pnl: float):
        """Notify when daily loss limit is hit"""
        message = (
            f"🛑 **DAILY LOSS LIMIT REACHED**\n\n"
            f"Today's Loss: ${daily_pnl:,.2f}\n\n"
            f"Trading stopped for today.\n"
            f"Will resume tomorrow."
        )
        await self.send_notification(message)

    async def notify_error(self, error_msg: str):
        """Notify about errors"""
        message = f"⚠️ **ERROR**\n\n{error_msg}"
        await self.send_notification(message)

    async def start_bot(self):
        """Start the Telegram bot"""
        try:
            self.app = Application.builder().token(self.token).build()

            # Add command handlers
            self.app.add_handler(CommandHandler("start", self.start_command))
            self.app.add_handler(CommandHandler("status", self.status_command))
            self.app.add_handler(CommandHandler("positions", self.positions_command))
            self.app.add_handler(CommandHandler("pnl", self.pnl_command))
            self.app.add_handler(CommandHandler("profit", self.pnl_command))  # Alias
            self.app.add_handler(CommandHandler("balance", self.balance_command))
            self.app.add_handler(CommandHandler("stop", self.stop_command))
            self.app.add_handler(CommandHandler("resume", self.resume_command))
            self.app.add_handler(CommandHandler("emergency", self.emergency_command))
            self.app.add_handler(CommandHandler("help", self.help_command))

            # Phase 2: Trade history and statistics commands
            self.app.add_handler(CommandHandler("trades", self.trades_command))
            self.app.add_handler(CommandHandler("winners", self.winners_command))
            self.app.add_handler(CommandHandler("losers", self.losers_command))
            self.app.add_handler(CommandHandler("stats", self.stats_command))
            self.app.add_handler(CommandHandler("export", self.export_command))

            # Add callback handlers
            self.app.add_handler(CallbackQueryHandler(self.pnl_callback, pattern='^pnl_'))
            self.app.add_handler(CallbackQueryHandler(self.stop_callback, pattern='^stop_'))
            self.app.add_handler(CallbackQueryHandler(self.emergency_callback, pattern='^emergency_'))

            # Start bot
            logger.info("Starting Telegram bot...")
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

            # Send startup notification
            await self.send_notification(
                "🤖 **Trading Bot Started**\n\n"
                "Bot is now running and monitoring markets.\n"
                "Use /help to see available commands."
            )

            logger.success("Telegram bot started successfully!")

        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            raise

    async def stop_bot(self):
        """Stop the Telegram bot"""
        try:
            if self.app:
                await self.send_notification("🛑 **Trading Bot Stopped**\n\nBot has shut down.")
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
                logger.info("Telegram bot stopped")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}")


if __name__ == "__main__":
    """Test Telegram bot"""
    import sys
    from config import Config

    if not Config.TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set in .env")
        print("Get a token from @BotFather on Telegram")
        sys.exit(1)

    if not Config.TELEGRAM_CHAT_ID:
        print("Error: TELEGRAM_CHAT_ID not set in .env")
        print("Get your chat ID from @userinfobot on Telegram")
        sys.exit(1)

    async def test():
        authorized_users = [int(Config.TELEGRAM_CHAT_ID)]
        bot = TelegramBot(Config.TELEGRAM_BOT_TOKEN, authorized_users)

        try:
            await bot.start_bot()
            print("\nTelegram bot is running!")
            print("Send /start to your bot to test it.")
            print("Press Ctrl+C to stop.\n")

            # Keep running
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print("\nStopping bot...")
            await bot.stop_bot()

    asyncio.run(test())
