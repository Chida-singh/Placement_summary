from telegram.ext import Updater, MessageHandler, Filters

# Replace this with your own bot token
BOT_TOKEN = "7507374617:AAElqVqe6YGHBXjgs9ms10MZqPbi7NW7ed4"

def handle_message(update, context):
    text = update.message.text
    update.message.reply_text("✅ Got your message!")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
