import openai
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext,Application,ApplicationBuilder
from dotenv import load_dotenv
import os
from db import CarFee
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine


load_dotenv()
# Set your API keys
OPENAI_API_KEY = os.getenv("OPENAI_CHAT_GPT_KEY") 
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_API_TOKEN")


# OpenAI Configuration
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Define a system prompt for the chatbot
SYSTEM_PROMPT = "Auction and vehicle history expert, proficient in platforms, repairs, and title processes. Users may provide car details from Carfax platform"

# Function to handle user messages
async def handle_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    chat_id = update.message.chat_id

    # Send the user message to OpenAI
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",     #"gpt-4",  # or "gpt-3.5-turbo"
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
    )
    print("""User: {}""".format(user_message))
    # Extract the bot's reply
    bot_reply = response.choices[0].message.content
    # bot_reply="Que volá, te gusta que te responda?"
    print("""Bot: {}""".format(bot_reply))
    # Send the reply back to the user on Telegram

    await context.bot.send_message(chat_id=chat_id, text=bot_reply)



async def fee_calculator(update: Update, context: CallbackContext):
    """
    estimate: the estimated value to be paid
    output: text with a table including all the fees. 
    
    """
    user_message = update.message.text
    chat_id = update.message.chat_id
    output="""
 ## Costo final estimado
   $9,560.00
 `* Este es solo un estimado y no el costo final.`
 ### Cost Breakdown

 |                   |           |
 | ----------------- | --------- |
 | Bid Amount        | $7,777.00 |
 | Buyer Fee         | $1,005.00 |
 | Gate Fee          | $79.00    |
 | Internet Bid Fee  | $119.00   |
 | Enviromental Fee  | $10.00    |
 | Title Mailing Fee | $20.00    |
 | Mapa Broker Fee   | $550.00   |
    
     """
    estimate = user_message
    titletype = user_message
    vehicletype = user_message
    paymenttype = user_message
    engine = create_engine('sqlite:///fees.db')
    Sesion = sessionmaker(bind=engine)
    session = Session()
    fee = sesion.query(CarFee).filter(CarFee.FinalBidMin<= estimate & CarFee.FinalBidMax>= estimate & CarFee.TitleType == titletype & CarFee.VehicleType == vehicletype & CarFee.PaymentType == paymenttype).first()

    # await context.bot.send_message(chat_id=chat_id, text=output,parse_mode='Markdown')



# Start the Telegram bot
def main():
    application=(
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    application.add_handler(CommandHandler("calcular_fees",fee_calculator))
    application.run_polling()
if __name__ == "__main__":
    main()
