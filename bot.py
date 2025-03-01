from telegram import Update, ChatMemberUpdated
from telegram.ext import Updater, CommandHandler, CallbackContext, ChatMemberHandler, MessageHandler, Filters
import logging
import pymongo
import os

# Load bot token from environment variable
TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')

# Connect to MongoDB
client = pymongo.MongoClient(MONGO_URI)
db = client['telegram_bot']
admin_collection = db['admins']
user_collection = db['users']

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to get admin list from MongoDB
def get_admins():
    return [admin['user_id'] for admin in admin_collection.find({}, {'_id': 0, 'user_id': 1})]

# Function to add a user to the database
def add_user(user_id):
    if not user_collection.find_one({'user_id': user_id}):
        user_collection.insert_one({'user_id': user_id})

# Auto-approve join requests
def handle_chat_member_update(update: Update, context: CallbackContext) -> None:
    chat_member = update.chat_member
    if chat_member.new_chat_member.status == 'restricted' and not chat_member.new_chat_member.is_member:
        context.bot.approve_chat_join_request(chat_member.chat.id, chat_member.new_chat_member.user.id)
        context.bot.send_message(chat_id=chat_member.new_chat_member.user.id, text="Your request to join has been approved. Welcome!")
        add_user(chat_member.new_chat_member.user.id)

# Auto-approve all pending join requests
def auto_accept_requests(update: Update, context: CallbackContext) -> None:
    chat_id = update.message.chat_id
    try:
        pending_requests = context.bot.get_chat_join_requests(chat_id)
        if pending_requests:
            for request in pending_requests:
                context.bot.approve_chat_join_request(chat_id, request.from_user.id)
                context.bot.send_message(chat_id=request.from_user.id, text="Your request to join has been approved. Welcome!")
                add_user(request.from_user.id)
            update.message.reply_text("All pending join requests have been approved.")
        else:
            update.message.reply_text("No pending join requests.")
    except Exception as e:
        logger.error(f"Failed to approve join requests: {e}")
        update.message.reply_text("Error processing join requests.")

# Broadcast message
def broadcast(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in get_admins():
        update.message.reply_text("You are not authorized to use this command.")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    for user in user_collection.find({}, {'user_id': 1}):
        try:
            context.bot.send_message(chat_id=user['user_id'], text=message)
        except Exception as e:
            logger.error(f"Failed to send message to {user['user_id']}: {e}")
    
    update.message.reply_text("Broadcast sent successfully.")

# Add admin
def add_admin(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in get_admins():
        update.message.reply_text("You are not authorized to use this command.")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /addadmin <user_id>")
        return
    
    new_admin_id = int(context.args[0])
    if new_admin_id not in get_admins():
        admin_collection.insert_one({'user_id': new_admin_id})
        update.message.reply_text(f"User {new_admin_id} is now an admin.")
    else:
        update.message.reply_text(f"User {new_admin_id} is already an admin.")

# Remove admin
def remove_admin(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_id not in get_admins():
        update.message.reply_text("You are not authorized to use this command.")
        return
    
    if not context.args:
        update.message.reply_text("Usage: /removeadmin <user_id>")
        return
    
    admin_id = int(context.args[0])
    if admin_id in get_admins():
        admin_collection.delete_one({'user_id': admin_id})
        update.message.reply_text(f"User {admin_id} has been removed as an admin.")
    else:
        update.message.reply_text(f"User {admin_id} is not an admin.")

# Start command
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Hello! I am your private bot. Only admins can control me.")

# Main function
def main() -> None:
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("broadcast", broadcast, pass_args=True))
    dispatcher.add_handler(CommandHandler("addadmin", add_admin, pass_args=True))
    dispatcher.add_handler(CommandHandler("removeadmin", remove_admin, pass_args=True))
    dispatcher.add_handler(CommandHandler("autoaccept", auto_accept_requests))
    dispatcher.add_handler(ChatMemberHandler(handle_chat_member_update))
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
