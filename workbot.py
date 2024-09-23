import logging
import nest_asyncio
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters, MessageHandler
from datetime import datetime
import json

# Allow nested asyncio event loops (important for interactive environments)
nest_asyncio.apply()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
TOKEN = "7810065533:AAEUH5zLQOSitQOORv0O1TyI7wMG8J3hjTs"

# Sample database structure to hold user data
user_data = {
    1476937429: {"rate": 0, "transactions": [], "daily_total": 0},
    1468222763: {"rate": 0, "transactions": [], "daily_total": 0}
}

# Admin list (default admins)
admins = {1476937429, 1468222763}

# Save data to a file (persistence)
def save_data():
    with open('user_data.json', 'w') as f:
        json.dump(user_data, f)

# Load data from file
def load_data():
    global user_data
    try:
        with open('user_data.json', 'r') as f:
            user_data = json.load(f)
    except FileNotFoundError:
        save_data()

# Ensure user exists in user_data dictionary
def ensure_user_exists(user_id):
    if user_id not in user_data:
        user_data[user_id] = {"rate": 0, "transactions": [], "daily_total": 0}

# Check if user is an admin
def is_admin(user_id):
    return user_id in admins

# Set exchange rate
async def setrate(update: Update, context: ContextTypes.DEFAULT_TYPE, args=None) -> None:
    user_id = update.effective_user.id
    ensure_user_exists(user_id)

    # Use provided args or context.args
    args = args or context.args

    try:
        rate = float(args[0])
        user_data[user_id]["rate"] = rate
        save_data()
        await update.message.reply_text(f"Exchange rate set to {rate}")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: .setrate <rate>")

# Record deal (dd command)
async def dd(update: Update, context: ContextTypes.DEFAULT_TYPE, args=None) -> None:
    user_id = update.effective_user.id
    ensure_user_exists(user_id)

    # Use provided args or context.args
    args = args or context.args

    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Usage: .dd <amount>")
        return
    
    amount_inr = int(args[0])
    rate = user_data[user_id].get("rate", 0)
    
    if rate == 0:
        await update.message.reply_text("Please set the exchange rate first using .setrate.")
        return
    
    usdt_amount = round(amount_inr / rate, 2)
    user_data[user_id]["transactions"].append((amount_inr, usdt_amount, str(datetime.now())))
    user_data[user_id]["daily_total"] += amount_inr
    save_data()

    # Generate message with current and total deposits
    total_inr = user_data[user_id]["daily_total"]
    total_usdt = round(total_inr / rate, 2)
    
    msg = (f"Current Issued {amount_inr} ({usdt_amount} USDT)\n"
           f"Issued History @{update.effective_user.username} (ID: {user_id})\n"
           f"Deposit today ({len(user_data[user_id]['transactions'])} transactions)\n\n"
           f"Total deposit: {total_inr} ({total_usdt} USDT)\n"
           f"Exchange rate: {rate}")
    
    await update.message.reply_text(msg)

# Reset all history (resetall command)
async def resetall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_user_exists(user_id)
    
    user_data[user_id]["transactions"] = []
    user_data[user_id]["daily_total"] = 0
    save_data()
    await update.message.reply_text(f"All transactions for today have been reset for @{update.effective_user.username} (ID: {user_id})")

# Display today's history (todayhistory command)
async def todayhistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_user_exists(user_id)
    
    transactions = user_data[user_id]["transactions"]
    if not transactions:
        await update.message.reply_text(f"No transactions recorded today for @{update.effective_user.username} (ID: {user_id}).")
        return

    rate = user_data[user_id]["rate"]
    total_inr = user_data[user_id]["daily_total"]
    total_usdt = round(total_inr / rate, 2)

    history_msg = (f"Total Issued Today for @{update.effective_user.username} (ID: {user_id}): {total_inr} ({total_usdt} USDT)\n")
    
    for idx, (inr, usdt, timestamp) in enumerate(transactions, start=1):
        history_msg += f"{idx}. {inr} ({usdt} USDT) at {timestamp}\n"
    
    history_msg += f"\nTotal deposit: {total_inr} ({total_usdt} USDT)\nExchange rate: {rate}"
    
    await update.message.reply_text(history_msg)

# Export all history to a .txt file (allhistory command)
async def allhistory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    ensure_user_exists(user_id)
    
    transactions = user_data[user_id]["transactions"]
    if not transactions:
        await update.message.reply_text(f"No transactions recorded for @{update.effective_user.username} (ID: {user_id}).")
        return
    
    file_content = f"Transaction History for @{update.effective_user.username} (ID: {user_id})\n\n"
    
    for idx, (inr, usdt, timestamp) in enumerate(transactions, start=1):
        file_content += f"{idx}. {inr} INR ({usdt} USDT) at {timestamp}\n"
    
    with open(f"{update.effective_user.username}_history.txt", "w") as file:
        file.write(file_content)
    
    with open(f"{update.effective_user.username}_history.txt", "rb") as file:
        await update.message.reply_document(document=file, filename=f"{update.effective_user.username}_history.txt")

# Export combined history for both users in a .txt file (bothtotal command)
async def bothtotal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    total_inr_all = 0
    total_usdt_all = 0
    file_content = "Combined Transaction History for Both Users\n\n"

    for user_id in user_data:
        user = user_data[user_id]
        total_inr = user["daily_total"]
        rate = user["rate"] if user["rate"] > 0 else 1  # Prevent division by zero
        total_usdt = round(total_inr / rate, 2)

        total_inr_all += total_inr
        total_usdt_all += total_usdt

        file_content += f"User ID: {user_id} (Username: @{update.effective_user.username})\nTotal Deposit: {total_inr} INR ({total_usdt} USDT)\nExchange rate: {rate}\n"
        file_content += "Transactions:\n"
        for idx, (inr, usdt, timestamp) in enumerate(user["transactions"], start=1):
            file_content += f"{idx}. {inr} INR ({usdt} USDT) at {timestamp}\n"
        file_content += "\n"

    # Add summary of total work for both users
    file_content += f"\nTotal Work Done Today:\nTotal Deposits: {total_inr_all} INR ({round(total_usdt_all, 2)} USDT)\n"

    # Save the file
    with open("combined_transaction_history.txt", "w") as file:
        file.write(file_content)

    # Send the file to the user
    with open("combined_transaction_history.txt", "rb") as file:
        await update.message.reply_document(document=file, filename="combined_transaction_history.txt")

# Show transaction count for each user (transactioncount command)
async def transactioncount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    transaction_count = {user_id: len(user["transactions"]) for user_id, user in user_data.items()}
    transaction_count_str = "Transaction Count:\n"
    for user_id, count in transaction_count.items():
        transaction_count_str += f"User ID: {user_id} (Username: @{update.effective_user.username}) - {count} transactions\n"
    await update.message.reply_text(transaction_count_str)

# Set a user as an admin (setadmin command)
async def setadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("You are not authorized to set an admin.")
        return

    try:
        new_admin_id = int(context.args[0])
        admins.add(new_admin_id)
        await update.message.reply_text(f"User ID {new_admin_id} is now an admin.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: .setadmin <user_id>")

# Show the list of admins (adminlist command)
async def adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_list_str = "List of Admins:\n" + "\n".join([f"User ID: {admin}" for admin in admins])
    await update.message.reply_text(admin_list_str)

# Convert USDT to INR or vice versa (convert command)
async def convert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        command_parts = update.message.text.split()
        amount = command_parts[1]
        rate = float(command_parts[2])

        if "usdt" in amount.lower():
            usdt_value = float(amount.lower().replace("usdt", ""))
            inr_value = usdt_value * rate
            await update.message.reply_text(f"{usdt_value} USDT = {inr_value:.2f} INR (Rate: {rate})")
        elif "inr" in amount.lower():
            inr_value = float(amount.lower().replace("inr", ""))
            usdt_value = inr_value / rate
            await update.message.reply_text(f"{inr_value} INR = {usdt_value:.2f} USDT (Rate: {rate})")
        else:
            await update.message.reply_text("Usage: .convert <amount><usdt/inr> <rate>")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: .convert <amount><usdt/inr> <rate>")

# Show the list of commands (cmd command)
async def cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    command_list = (
        ".setrate <rate> - Set exchange rate of USDT\n"
        ".dd <amount> - Record a transaction in INR\n"
        ".resetall - Reset your daily transaction history\n"
        ".todayhistory - Show today's transaction history\n"
        ".allhistory - Export all transaction history to a .txt file\n"
        ".bothtotal - Export combined transaction history for both users to a .txt file\n"
        ".transactioncount - Shows number of transactions for each user\n"
        ".setadmin <user_id> - Set a user as admin\n"
        ".adminlist - Show list of admins\n"
        ".convert <amount><usdt/inr> <rate> - Convert USDT to INR or vice versa\n"
        ".cmd - Display this list of commands"
    )
    await update.message.reply_text(command_list)

# Function to handle commands starting with "." or "/"
async def handle_dot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    if message_text.startswith('.'):
        message_text = '/' + message_text[1:]  # Replace . with /

    command_parts = message_text.split()
    command = command_parts[0]
    args = command_parts[1:]

    # Simulate command processing with extracted args
    if command.startswith("/setrate"):
        await setrate(update, context, args)
    elif command.startswith("/dd"):
        await dd(update, context, args)
    elif command.startswith("/resetall"):
        await resetall(update, context)
    elif command.startswith("/todayhistory"):
        await todayhistory(update, context)
    elif command.startswith("/allhistory"):
        await allhistory(update, context)
    elif command.startswith("/bothtotal"):
        await bothtotal(update, context)
    elif command.startswith("/transactioncount"):
        await transactioncount(update, context)
    elif command.startswith("/setadmin"):
        await setadmin(update, context)
    elif command.startswith("/adminlist"):
        await adminlist(update, context)
    elif command.startswith("/convert"):
        await convert(update, context)
    elif command.startswith("/cmd"):
        await cmd(update, context)

# Main function to start the bot
async def main():
    # Create the Application and pass it the bot's token.
    application = Application.builder().token(TOKEN).build()

    # Load previous data
    load_data()

    # Command handlers
    application.add_handler(CommandHandler("setrate", setrate))
    application.add_handler(CommandHandler("dd", dd))
    application.add_handler(CommandHandler("resetall", resetall))
    application.add_handler(CommandHandler("todayhistory", todayhistory))
    application.add_handler(CommandHandler("allhistory", allhistory))
    application.add_handler(CommandHandler("bothtotal", bothtotal))
    application.add_handler(CommandHandler("transactioncount", transactioncount))
    application.add_handler(CommandHandler("setadmin", setadmin))
    application.add_handler(CommandHandler("adminlist", adminlist))
    application.add_handler(CommandHandler("convert", convert))
    application.add_handler(CommandHandler("cmd", cmd))

    # Handle messages that start with "."
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^\."), handle_dot_command))

    # Start the bot using polling
    logger.info("Bot is starting and polling for updates...")
    await application.run_polling()

if __name__ == "__main__":
    # Use the already running event loop to avoid the error in VSCode/Notebooks
    loop = asyncio.get_event_loop()
    if not loop.is_running():
        loop.run_until_complete(main())
    else:
        # If the event loop is already running, run the main function inside it
        loop.create_task(main())
