"""
Telegram Bot Integration for Trading Bot
Provides remote control and monitoring via Telegram
"""
import asyncio
from datetime import datetime, timedelta
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
            "**Available Commands:**\n"
            "/status - Bot status and summary\n"
            "/positions - View open positions\n"
            "/pnl - Profit & Loss report\n"
            "/balance - Account balance\n"
            "/stop - Stop trading gracefully\n"
            "/resume - Resume trading\n"
            "/emergency - Emergency stop (close all)\n"
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
        """Handle /pnl command with time period selection"""
        if not self.is_authorized(update.effective_user.id):
            return

        keyboard = [
            [
                InlineKeyboardButton("📅 Daily", callback_data='pnl_daily'),
                InlineKeyboardButton("📊 Weekly", callback_data='pnl_weekly')
            ],
            [
                InlineKeyboardButton("📈 Monthly", callback_data='pnl_monthly'),
                InlineKeyboardButton("🏆 All Time", callback_data='pnl_alltime')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "📊 **Select Time Period:**",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        self.commands_executed += 1

    async def pnl_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle P&L button callbacks"""
        query = update.callback_query
        await query.answer()

        if not self.is_authorized(query.from_user.id):
            return

        try:
            period = query.data.replace('pnl_', '')

            if not self.trading_bot:
                await query.edit_message_text("⚠️ Trading bot not connected")
                return

            summary = self.trading_bot.risk_manager.get_portfolio_summary()

            # Calculate period-specific stats (simplified - you'd want to track this in DB)
            message = ""

            if period == 'daily':
                message = (
                    "📅 **DAILY P&L REPORT**\n\n"
                    f"💰 Today's P&L: ${summary['daily_pnl']:,.2f}\n"
                    f"📊 Trades Today: {summary['daily_trades']}\n"
                    f"✅ Wins: {summary['winning_trades']}\n"
                    f"❌ Losses: {summary['losing_trades']}\n"
                    f"📈 Win Rate: {summary['win_rate']:.1f}%\n\n"
                )
                from config import Config
                progress = (summary['daily_pnl'] / Config.TARGET_DAILY_PROFIT) * 100
                message += f"🎯 Target Progress: {progress:.0f}%\n"
                message += f"Target: ${Config.TARGET_DAILY_PROFIT:.2f}\n"
                message += f"Max Loss: ${Config.MAX_DAILY_LOSS:.2f}"

            elif period == 'alltime':
                message = (
                    "🏆 **ALL TIME P&L REPORT**\n\n"
                    f"💰 Total P&L: ${summary['total_pnl']:,.2f}\n"
                    f"📈 Return: {summary['total_pnl_pct']:+.2f}%\n"
                    f"📊 Total Trades: {summary['total_trades']}\n"
                    f"✅ Winning: {summary['winning_trades']}\n"
                    f"❌ Losing: {summary['losing_trades']}\n"
                    f"📈 Win Rate: {summary['win_rate']:.1f}%\n\n"
                    f"💵 Initial: ${summary['initial_balance']:,.2f}\n"
                    f"💰 Current: ${summary['balance']:,.2f}\n"
                    f"📊 Portfolio: ${summary['portfolio_value']:,.2f}"
                )

            else:
                # Weekly/Monthly would require historical tracking
                message = (
                    f"📊 **{period.upper()} P&L REPORT**\n\n"
                    f"⚠️ Historical tracking not yet implemented.\n"
                    f"Current session stats:\n\n"
                    f"💰 P&L: ${summary['total_pnl']:,.2f}\n"
                    f"📊 Trades: {summary['total_trades']}\n"
                    f"📈 Win Rate: {summary['win_rate']:.1f}%"
                )

            await query.edit_message_text(message, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in P&L callback: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

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
            "**Monitoring:**\n"
            "/status - Bot status and summary\n"
            "/positions - View open positions\n"
            "/pnl - P&L reports (daily/weekly/monthly/all-time)\n"
            "/balance - Account balance\n\n"
            "**Control:**\n"
            "/stop - Stop trading (keep positions)\n"
            "/resume - Resume trading\n"
            "/emergency - Emergency stop (close all)\n\n"
            "**Other:**\n"
            "/help - Show this help message\n\n"
            "**Notifications:**\n"
            "You'll receive automatic notifications for:\n"
            "• Trades opened/closed\n"
            "• Daily targets reached\n"
            "• Important alerts\n\n"
            "**Security:**\n"
            "Only authorized users can control this bot.\n"
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
                return

            for user_id in self.authorized_users:
                try:
                    await self.app.bot.send_message(
                        chat_id=user_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    self.notifications_sent += 1
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
