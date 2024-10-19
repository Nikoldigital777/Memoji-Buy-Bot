# Moji Buy Bot

Moji Buy Bot is a Telegram bot designed to facilitate cryptocurrency transactions, tipping, and price tracking for the Moji token. It offers a range of features including emoji-based tipping, wallet management, and integration with blockchain technology.

## Features

- **Price Tracking**: Get real-time Moji token price and market cap information.
- **Chart Viewing**: Access Moji price charts directly from the bot.
- **Emoji Tipping**: Send tips to other users using customizable emoji for each group.
- **Wallet Management**: Create and manage Moji wallets securely within the bot.
- **Drip Tipping**: Send tips to all active users in a group simultaneously.
- **Blockchain Integration**: Interact with the Moji token smart contract on the blockchain.
- **AI-Powered Responses**: Enjoy quirky AI-generated responses for invalid commands.

## Commands

- `/start` - Welcome message and introduction
- `/help` - Display available commands and their usage
- `/price` - Get current Moji price and market cap
- `/chart` - Get a link to the Moji price chart
- `/send <amount> @<username>` - Send a tip to another user
- `/balance` - Check your Moji balance (only in private chat)
- `/drip <amount>` - Send a tip to all registered users
- `/enchant` - Generate wallet keys (only in private chat)
- `/withdraw <amount> <address>` - Withdraw Moji to a unicorn1 wallet
- `/disclaimer` - View the bot's disclaimer

## Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/moji-buy-bot.git
   cd moji-buy-bot
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables in a `.env` file:
   ```
   DATABASE_URL=your_database_url
   REDIS_HOST=your_redis_host
   REDIS_PORT=your_redis_port
   BLOCKCHAIN_RPC_URL=your_blockchain_rpc_url
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   CHART_BASE_URL=https://uwu.pro
   ENCRYPTION_KEY=your_encryption_key
   TOGETHER_AI_API_KEY=your_together_ai_api_key
   MOJI_CONTRACT_ADDRESS=your_moji_contract_address
   MOJI_CONTRACT_ABI=your_moji_contract_abi
   ```

4. Initialize the database:
   ```
   python init_db.py
   ```

5. Run the bot:
   ```
   python main.py
   ```

## Usage

1. Start a chat with the bot on Telegram.
2. Use `/start` to get an introduction and `/help` to see available commands.
3. Create a wallet using `/enchant` in a private chat with the bot.
4. Use `/price` and `/chart` to get Moji token information.
5. Send tips to other users with the `/send` command or emoji tipping.
6. Use `/drip` to send tips to all active users in a group.
7. Withdraw your Moji tokens to a unicorn1 wallet using `/withdraw`.

## Security

- Private keys are encrypted before storage.
- Sensitive commands are restricted to private chats.
- Always keep your private keys secure and never share them.

## Disclaimer

This bot is for informational purposes only. Do not make investment decisions based solely on the information provided by this bot. Always do your own research before investing. The bot creators are not responsible for any financial losses incurred.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the (LICENSE) file for details.
