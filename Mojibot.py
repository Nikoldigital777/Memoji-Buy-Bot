import os
from dotenv import load_dotenv
from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from web3 import Web3
from decimal import Decimal, InvalidOperation
import logging
import re
import requests
from cryptography.fernet import Fernet
from eth_account import Account
import openai
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration from environment
DATABASE_URL = os.getenv('DATABASE_URL')
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT'))
BLOCKCHAIN_RPC_URL = os.getenv('BLOCKCHAIN_RPC_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHART_BASE_URL = os.getenv('CHART_BASE_URL', 'https://uwu.pro')
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
TOGETHER_AI_API_KEY = os.getenv('TOGETHER_AI_API_KEY')
MOJI_CONTRACT_ADDRESS = os.getenv('MOJI_CONTRACT_ADDRESS')
MOJI_CONTRACT_ABI = json.loads(os.getenv('MOJI_CONTRACT_ABI'))

# Database setup
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True)
    username = Column(String)
    wallet = relationship("Wallet", uselist=False, back_populates="user")
    transactions = relationship("Transaction", back_populates="user")
    last_active = Column(DateTime, default=datetime.utcnow)

class Wallet(Base):
    __tablename__ = 'wallets'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    address = Column(String, unique=True)
    encrypted_private_key = Column(String)
    balance = Column(Float, default=0.0)
    user = relationship("User", back_populates="wallet")

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    amount = Column(Float)
    transaction_type = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="transactions")

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String, unique=True)
    tipping_emoji = Column(String, default='🦄')
    bot_name = Column(String, default='Moji Buy Bot')
    bot_profile_pic = Column(String)

engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db_session = Session()

# Web3 and encryption setup
w3 = Web3(Web3.HTTPProvider(BLOCKCHAIN_RPC_URL))
fernet = Fernet(ENCRYPTION_KEY.encode())

# Set up Together.ai API
openai.api_key = TOGETHER_AI_API_KEY

# Services
class PriceService:
    def get_current_price(self) -> Decimal:
        response = requests.get('https://api.example.com/moji_price')
        if response.status_code == 200:
            data = response.json()
            return Decimal(data['price'])
        else:
            raise Exception("Unable to fetch price from API")

    def get_market_cap(self) -> Decimal:
        total_supply = self.get_total_supply()
        price = self.get_current_price()
        return total_supply * price

    def get_total_supply(self) -> Decimal:
        contract = w3.eth.contract(address=MOJI_CONTRACT_ADDRESS, abi=MOJI_CONTRACT_ABI)
        total_supply = contract.functions.totalSupply().call()
        return Decimal(total_supply) / Decimal(10**6)  # Assuming 6 decimal places

class WalletService:
    def create_wallet(self, user_id: int) -> dict:
        account = Account.create()
        private_key = account.privateKey.hex()
        encrypted_private_key = fernet.encrypt(private_key.encode()).decode()
        address = account.address
        
        user = db_session.query(User).filter_by(telegram_id=str(user_id)).first()
        if not user:
            user = User(telegram_id=str(user_id))
            db_session.add(user)
        
        wallet = Wallet(user=user, address=address, encrypted_private_key=encrypted_private_key)
        db_session.add(wallet)
        db_session.commit()
        
        return {"private_key": private_key, "address": address}

    def get_balance(self, user_id: int) -> Decimal:
        user = db_session.query(User).filter_by(telegram_id=str(user_id)).first()
        if user and user.wallet:
            contract = w3.eth.contract(address=MOJI_CONTRACT_ADDRESS, abi=MOJI_CONTRACT_ABI)
            balance = contract.functions.balanceOf(user.wallet.address).call()
            return Decimal(balance) / Decimal(10**6)  # Assuming 6 decimal places
        return Decimal('0')

    def withdraw(self, user_id: int, amount: Decimal, to_address: str) -> str:
        user = db_session.query(User).filter_by(telegram_id=str(user_id)).first()
        if not user or not user.wallet:
            return "Wallet not found. Please use /enchant to create a wallet."

        if not w3.isAddress(to_address):
            return "Invalid unicorn1 wallet address."

        balance = self.get_balance(user_id)
        if balance < amount:
            return f"Insufficient balance. Your current balance is {balance} MOJI."

        try:
            contract = w3.eth.contract(address=MOJI_CONTRACT_ADDRESS, abi=MOJI_CONTRACT_ABI)
            private_key = fernet.decrypt(user.wallet.encrypted_private_key.encode()).decode()
            
            nonce = w3.eth.get_transaction_count(user.wallet.address)
            txn = contract.functions.transfer(
                to_address,
                int(amount * Decimal(10**6))
            ).buildTransaction({
                'chainId': 1,  # Mainnet. Change if using a different network
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
            })
            
            signed_txn = w3.eth.account.sign_transaction(txn, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Record the transaction
            transaction = Transaction(user=user, amount=-float(amount), transaction_type='withdraw')
            db_session.add(transaction)
            db_session.commit()
            
            return f"Withdrawal of {amount} MOJI to {to_address} initiated. Transaction hash: {tx_hash.hex()}"
        except Exception as e:
            logger.error(f"Withdrawal error: {str(e)}")
            return "An error occurred during withdrawal. Please try again later."

class ChartService:
    def __init__(self, base_url: str = CHART_BASE_URL):
        self.base_url = base_url

    def get_chart_url(self) -> str:
        return f"{self.base_url}/chart/moji"

class TippingService:
    def __init__(self, wallet_service: WalletService):
        self.wallet_service = wallet_service

    def send_tip(self, sender_id: int, recipient: str, amount: Decimal) -> str:
        sender = db_session.query(User).filter_by(telegram_id=str(sender_id)).first()
        recipient = db_session.query(User).filter_by(username=recipient).first()

        if not sender or not recipient:
            return "Sender or recipient not found."

        sender_balance = self.wallet_service.get_balance(sender_id)
        if sender_balance < amount:
            return f"Insufficient balance. Your current balance is {sender_balance} MOJI."

        try:
            contract = w3.eth.contract(address=MOJI_CONTRACT_ADDRESS, abi=MOJI_CONTRACT_ABI)
            sender_private_key = fernet.decrypt(sender.wallet.encrypted_private_key.encode()).decode()
            
            nonce = w3.eth.get_transaction_count(sender.wallet.address)
            txn = contract.functions.transfer(
                recipient.wallet.address,
                int(amount * Decimal(10**6))
            ).buildTransaction({
                'chainId': 1,  # Mainnet. Change if using a different network
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'nonce': nonce,
            })
            
            signed_txn = w3.eth.account.sign_transaction(txn, sender_private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Record the transactions
            sender_transaction = Transaction(user=sender, amount=-float(amount), transaction_type='tip_sent')
            recipient_transaction = Transaction(user=recipient, amount=float(amount), transaction_type='tip_received')
            db_session.add(sender_transaction)
            db_session.add(recipient_transaction)
            db_session.commit()
            
            return f"Sent {amount} MOJI to @{recipient.username}. Transaction hash: {tx_hash.hex()}"
        except Exception as e:
            logger.error(f"Tipping error: {str(e)}")
            return "An error occurred while sending the tip. Please try again later."

    def drip_tip(self, sender_id: int, amount: Decimal) -> str:
        sender = db_session.query(User).filter_by(telegram_id=str(sender_id)).first()
        if not sender:
            return "Sender not found."

        active_users = db_session.query(User).filter(User.wallet != None, User.last_active > (datetime.utcnow() - timedelta(days=7))).all()
        active_user_count = len(active_users) - 1  # Exclude sender

        if active_user_count == 0:
            return "No active users to drip tip."

        amount_per_user = (amount / active_user_count).quantize(Decimal('0.000001'))
        total_amount = amount_per_user * active_user_count

        sender_balance = self.wallet_service.get_balance(sender_id)
        if sender_balance < total_amount:
            return f"Insufficient balance for drip tipping. You need at least {total_amount} MOJI."

        try:
            contract = w3.eth.contract(address=MOJI_CONTRACT_ADDRESS, abi=MOJI_CONTRACT_ABI)
            sender_private_key = fernet.decrypt(sender.wallet.encrypted_private_key.encode()).decode()
            
            for user in active_users:
                if user.id != sender.id:
                    nonce = w3.eth.get_transaction_count(sender.wallet.address)
                    txn = contract.functions.transfer(
                        user.wallet.address,
                        int(amount_per_user * Decimal(10**6))
                    ).buildTransaction({
                        'chainId': 1,  # Mainnet. Change if using a different network
                        'gas': 100000,
                        'gasPrice': w3.eth.gas_price,
                        'nonce': nonce,
                    })
                    
                    signed_txn = w3.eth.account.sign_transaction(txn, sender_private_key)
                    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    
                    # Record the transactions
                    sender_transaction = Transaction(user=sender, amount=-float(amount_per_user), transaction_type='drip_sent')
                    recipient_transaction = Transaction(user=user, amount=float(amount_per_user), transaction_type='drip_received')
                    db_session.add(sender_transaction)
                    db_session.add(recipient_transaction)
            
            db_session.commit()
            return f"🌧️ Drip tip of {amount_per_user} MOJI sent to {active_user_count} users successfully!"
        except Exception as e:
            logger.error(f"Drip tipping error: {str(e)}")
            return "An error occurred during drip tipping. Please try again later."

class EmojiTippingSystem:
    def __init__(self, tipping_service: TippingService):
        self.tipping_service = tipping_service

    def process_emoji_tip(self, update: Update, context: CallbackContext) -> None:
        group_id = update.effective_chat.id
        sender_id = update.effective_user.id
        message_text = update.message.text

        group = db_session.query(Group).filter_by(telegram_id=str(group_id)).first()
        if not group:
            group = Group(telegram_id=str(group_id))
            db_session.add(group)
            db_session.commit()

        group_emoji = group.tipping_emoji
        if group_emoji not in message_text:
            return  # Not a tipping message

        pattern = rf"(?P<amount>\d+(\.\d{{1,6}})?)?\s*{re.escape(group_emoji)}\s*@(?P<recipient>\w+)"
        match = re.search(pattern, message_text)
        if not match:
            update.message.reply_text("Invalid tipping format. Use: [amount] emoji @recipient")
            return

        amount_str = match.group('amount')
        recipient = match.group('recipient')

        try:
            amount = Decimal(amount_str) if amount_str else Decimal('1')
            result = self.tipping_service.send_tip(sender_id, recipient, amount)
            update.message.reply_text(result)
        except InvalidOperation:
            update.message.reply_text("Invalid amount. Please enter a valid number.")
        except Exception as e:
            update.message.reply_text("An error occurred while processing the tip.")

    def process_invalid_command(self, update: Update, context: CallbackContext) -> None:
        try:
            response = openai.Completion.create(
                model="gpt-3.5-turbo",
                prompt=f"A user entered an invalid command: {update.message.text}. Respond with a sassy but friendly message.",
                max_tokens=50
            )
            sassy_reply = response.choices[0].text.strip()
            update.message.reply_text(sassy_reply)
        except Exception as e:
            logger.error(f"Error in process_invalid_command: {str(e)}")
            update.message.reply_text("Oops, something went wrong. Even AI can have bad days!")

# Handlers
class BotHandlers:
    def __init__(self, price_service, chart_service, wallet_service, tipping_service, emoji_tipping_system):
        self.price_service = price_service
        self.chart_service = chart_service
        self.wallet_service = wallet_service
        self.tipping_service = tipping_service
        self.emoji_tipping_system = emoji_tipping_system

    def start_handler(self, update: Update, context: CallbackContext) -> None:
        update.message.reply_text("Welcome to Moji Buy Bot! Use /help to see available commands.")

    def help_handler(self, update: Update, context: CallbackContext) -> None:
        help_text = """
Available commands:
/price - Get current Moji price and market cap
/chart - Get a link to the Moji price chart
/send <amount> @<username> - Send a tip to another user
/balance - Check your Moji balance (only in private chat)
/drip <amount> - Send a tip to all registered users
/enchant - Generate wallet keys (only in private chat)
/withdraw <amount> <address> - Withdraw Moji to a unicorn1 wallet
/disclaimer - View the bot's disclaimer
        """
        update.message.reply_text(help_text)

    def disclaimer_handler(self, update: Update, context: CallbackContext) -> None:
        disclaimer_text = """
⚠️ Disclaimer:
This bot is for informational purposes only. Do not make investment decisions based solely on the information provided by this bot. Always do your own research before investing. The bot creators are not responsible for any financial losses incurred.
        """
        update.message.reply_text(disclaimer_text)

    def enchant_handler(self, update: Update, context: CallbackContext) -> None:
        if update.effective_chat.type != 'private':
            update.message.reply_text("Please use the /enchant command in a private message for security.")
            return

        try:
            wallet_info = self.wallet_service.create_wallet(update.effective_user.id)
            update.message.reply_text(
                f"🔮 Your new wallet has been enchanted!

"
                f"Address: `{wallet_info['address']}`

"
                f"Private Key: `{wallet_info['private_key']}`

"
                "⚠️ IMPORTANT: Store this information securely. It will not be shown again!",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Error in enchant_handler: {str(e)}")
            update.message.reply_text("Unable to generate wallet. Please try again later.")

    def withdraw_handler(self, update: Update, context: CallbackContext) -> None:
        try:
            if len(context.args) != 2:
                raise ValueError("Incorrect number of arguments.")

            amount = Decimal(context.args[0])
            address = context.args[1]

            result = self.wallet_service.withdraw(update.effective_user.id, amount, address)
            update.message.reply_text(result)
        except (ValueError, InvalidOperation) as e:
            update.message.reply_text(f"Error: {str(e)}
Usage: /withdraw <amount> <unicorn1 address>")
        except Exception as e:
            logger.error(f"Error in withdraw_handler: {str(e)}")
            update.message.reply_text("An unexpected error occurred. Please try again later.")

    def drip_handler(self, update: Update, context: CallbackContext) -> None:
        try:
            if len(context.args) != 1:
                raise ValueError("Incorrect number of arguments.")

            amount = Decimal(context.args[0])
            result = self.tipping_service.drip_tip(update.effective_user.id, amount)
            update.message.reply_text(result)
        except (ValueError, InvalidOperation) as e:
            update.message.reply_text(f"Error: {str(e)}
Usage: /drip <tip amount>")
        except Exception as e:
            logger.error(f"Error in drip_handler: {str(e)}")
            update.message.reply_text("An unexpected error occurred. Please try again later.")

    def price_handler(self, update: Update, context: CallbackContext) -> None:
        try:
            price = self.price_service.get_current_price()
            market_cap = self.price_service.get_market_cap()
            message = f"💰 Current Moji price: ${price:.6f}\n📊 Market Cap: ${market_cap:.2f}"
            update.message.reply_text(message)
        except Exception as e:
            logger.error(f"Error in price_handler: {str(e)}")
            update.message.reply_text("Unable to fetch price information. Please try again later.")

    def chart_handler(self, update: Update, context: CallbackContext) -> None:
        chart_url = self.chart_service.get_chart_url()
        update.message.reply_text(f"📈 View the Moji price chart here: {chart_url}")

    def send_handler(self, update: Update, context: CallbackContext) -> None:
        try:
            if len(context.args) != 2:
                raise ValueError("Incorrect number of arguments.")

            amount = Decimal(context.args[0])
            recipient = context.args[1]

            if not recipient.startswith('@'):
                raise ValueError("Recipient must be a valid @username.")

            recipient = recipient[1:]  # Remove the '@' symbol

            result = self.tipping_service.send_tip(update.effective_user.id, recipient, amount)
            update.message.reply_text(result)
        except (ValueError, InvalidOperation) as e:
            update.message.reply_text(f"Error: {str(e)}\nUsage: /send <tip amount> @<username>")
        except Exception as e:
            logger.error(f"Error in send_handler: {str(e)}")
            update.message.reply_text("An unexpected error occurred. Please try again later.")

    def balance_handler(self, update: Update, context: CallbackContext) -> None:
        if update.effective_chat.type != 'private':
            update.message.reply_text("Please check your balance in a private message.")
            return

        try:
            balance = self.wallet_service.get_balance(update.effective_user.id)
            update.message.reply_text(f"💼 Your current balance is: {balance:.6f} Moji")
        except Exception as e:
            logger.error(f"Error in balance_handler: {str(e)}")
            update.message.reply_text("Unable to fetch balance. Please try again later.")

    def unknown_command_handler(self, update: Update, context: CallbackContext) -> None:
        self.emoji_tipping_system.process_invalid_command(update, context)

# Main function to start the bot
class BuyBotLayout:
    @staticmethod
    def format_buy_message(transaction: dict) -> str:
        return f"""
🎉 New Moji Purchase! 🎉
🦄 Spent: {transaction['spent']}
📥 Received: {transaction['received']} MOJI
👛 Buyer Holdings: {transaction['buyer_holdings']} MOJI
💰 Price: ${transaction['price']:.6f}
📊 Market Cap: ${transaction['market_cap']:.2f}
        """

def main():
    # Initialize services
    price_service = PriceService()
    chart_service = ChartService()
    wallet_service = WalletService()
    tipping_service = TippingService(wallet_service)
    emoji_tipping_system = EmojiTippingSystem(tipping_service)

    # Initialize bot handlers
    handlers = BotHandlers(
        price_service=price_service,
        chart_service=chart_service,
        wallet_service=wallet_service,
        tipping_service=tipping_service,
        emoji_tipping_system=emoji_tipping_system
    )

    # Set up Telegram bot
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add command handlers
    dp.add_handler(CommandHandler("start", handlers.start_handler))
    dp.add_handler(CommandHandler("help", handlers.help_handler))
    dp.add_handler(CommandHandler("disclaimer", handlers.disclaimer_handler))
    dp.add_handler(CommandHandler("enchant", handlers.enchant_handler))
    dp.add_handler(CommandHandler("withdraw", handlers.withdraw_handler))
    dp.add_handler(CommandHandler("drip", handlers.drip_handler))
    dp.add_handler(CommandHandler("price", handlers.price_handler))
    dp.add_handler(CommandHandler("chart", handlers.chart_handler))
    dp.add_handler(CommandHandler("send", handlers.send_handler))
    dp.add_handler(CommandHandler("balance", handlers.balance_handler))

    # Add message handler for emoji tipping
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, emoji_tipping_system.process_emoji_tip))

    # Add handler for unknown commands
    dp.add_handler(MessageHandler(Filters.command, handlers.unknown_command_handler))

    # Start the bot
    logger.info("Starting Moji Buy Bot...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception: {str(e)}", exc_info=True)
