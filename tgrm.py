import openai
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext,Application,ApplicationBuilder
from dotenv import load_dotenv
import os
from db import CarFee,ConversationManager
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from datetime import datetime 
import yaml

load_dotenv()
# Set your API keys
OPENAI_API_KEY = os.getenv("OPENAI_CHAT_GPT_KEY") 
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_API_TOKEN")


# OpenAI Configuration
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Define a system prompt for the chatbot
SYSTEM_PROMPT = "Act as an auction and vehicle history expert, proficient in platforms, repairs, and title processes. Users may provide car details from Carfax platform to get the most aproximate estimate of a car value for optimizing bidding in auction sales."


engine = create_engine('sqlite:///carfaxbot.db')
Session = sessionmaker(bind=engine)

Conversations = ConversationManager()

# Function to handle user messages
async def handle_message(update: Update, context: CallbackContext):
    user_message = update.message.text
    chat_id = update.message.chat_id

    if not Conversations.check_chat_in_db(chat_id):
        Conversations.add_chat(chat_id,"message") 

    current_chat= Conversations.get_chat(chat_id)
    if current_chat['current_chat_mode'] == 'calcular_fees':
        await fee_calculator(update,context)
        return 
    # force Update chat state and datetime 
    # Conversations.set_chat_property(chat_id,'last_interaction',datetime.now() )
    # Conversations.set_chat_property(chat_id,'current_chat_mode','message')
    
    # Send the user message to OpenAI
    response = client.chat.completions.create(
        model="gpt-4", #"gpt-3.5-turbo",     #  # or "gpt-3.5-turbo"
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
    with open('questions.yml','r') as file:
        questions = yaml.safe_load(file)['calcular_fees']


    if not Conversations.check_chat_in_db(chat_id):
        Conversations.add_chat(chat_id,"calcular_fees")
    else:
        Conversations.set_chat_property(chat_id,'current_chat_mode','calcular_fees')

    if not Conversations.check_conversation_in_db(chat_id):
        Conversations.add_conversation(chat_id)
    
    active_conversation_list = Conversations.get_unfinished_conversations(chat_id)

    # clean the database of dangling open conversations other than the last one
    if len(active_conversation_list) >1:
        active_conversation = active_conversation_list.pop()
        for ac in active_conversation_list:
             Conversations.finish_conversation(ac.conversation_id)
    elif len(active_conversation_list) == 0 :
        Conversations.add_conversation(chat_id)
        active_conversation_list = Conversations.get_unfinished_conversations(chat_id)
        active_conversation = active_conversation_list.pop()
    else:
        active_conversation = active_conversation_list.pop()

    current_context_messages = Conversations.get_active_conversation_questions(active_conversation.conversation_id)

    if len(current_context_messages) == 0:
        qorder = 1
        Conversations.add_answer_message(active_conversation.conversation_id,questions[qorder],"",qorder)
        await context.bot.send_message(chat_id=chat_id, text=questions[qorder])

    elif len(current_context_messages) == len(questions.keys()):
        previous_question = current_context_messages[-1]
        previous_answer   = user_message
        # Conversations.add_answer_message(active_conversation.conversation_id,questions[qorder],"",qorder)
        Conversations.set_question_property(previous_question.id,"answer",previous_answer)
        Conversations.finish_conversation(active_conversation.conversation_id)           # Finalizar la conversación cuando tenga todoss los datos
        
    else:
        previous_question = current_context_messages[-1]
        previous_answer   = user_message
        Conversations.set_question_property(previous_question.id,"answer",previous_answer)

        qorder  = previous_question.qorder +1
        Conversations.add_answer_message(active_conversation.conversation_id,questions[qorder],"",qorder)
        await context.bot.send_message(chat_id=chat_id, text=questions[qorder])
    


    Conversations.set_chat_property(chat_id,'last_interaction',datetime.now() )
    if active_conversation.finished == True:
        # force Update chat state and datetime 
        Conversations.set_chat_property(chat_id,'current_chat_mode','message')
    

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
    estimate = 1500
    titletype = 'Clean'
    vehicletype = 'Standard'
    paymenttype = 'Secure'

    # # Send messages to the user asking for input values
    # await context.bot.send_message(chat_id=chat_id, text="Please enter the estimated value of the car:")
    
    # async def get_estimate(update: Update, context: CallbackContext):
    #     nonlocal estimate
    #     estimate = update.message.text
    #     await context.bot.send_message(chat_id=chat_id, text="What is the type of title (Clean, Salvage, etc.)?")
        
    #     async def get_title_type(update: Update, context: CallbackContext):
    #         nonlocal titletype
    #         titletype = update.message.text
    #         await context.bot.send_message(chat_id=chat_id, text="What is the make and model of the vehicle?")
            
    #         async def get_vehicletype(update: Update, context: CallbackContext):
    #             nonlocal vehicletype
    #             vehicletype = update.message.text
    #             await context.bot.send_message(chat_id=chat_id, text="What type of payment (Cash, Credit Card, etc.) are you making?")
                
    #             async def get_payment_type(update: Update, context: CallbackContext):
    #                 nonlocal paymenttype
    #                 paymenttype = update.message.text
                    
    #                 # Use the provided values to calculate the fee and output a message with a table
    #                 estimate = float(estimate)
    #                 titletype = titletype
    #                 vehicletype = vehicletype
    #                 paymenttype = paymenttype
                    
    #                 output=f""" """
    #                 await context.bot.send_message(chat_id=chat_id, text=output)

    #             await get_payment_type()

    #         await get_vehicletype()

    #     await get_title_type()

    # await get_estimate()


    # session = Session()
    # fee = session.query(CarFee).filter(CarFee.FinalBidMin<= estimate, CarFee.FinalBidMax>= estimate , CarFee.TitleType == titletype,CarFee.VehicleType == vehicletype , CarFee.PaymentType == paymenttype).first()
    # # await context.bot.send_message(chat_id=chat_id, text=output,parse_mode='Markdown')

async def finish_conversation(conversation_id):
    Conversations.finish_conversation(conversation_id)
async def create_new_answer_message(conversation_id,question,answer,qorder):
    Conversations.add_answer_message(conversation_id,question,answer,qorder)



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
