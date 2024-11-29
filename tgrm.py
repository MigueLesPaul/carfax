import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup,ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext,Application,ApplicationBuilder
from dotenv import load_dotenv
import os
from db import CarFee,ConversationManager
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from datetime import datetime 
import yaml
import numpy as np

load_dotenv()
# Set your API keys
OPENAI_API_KEY = os.getenv("OPENAI_CHAT_GPT_KEY") 
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_API_TOKEN")


# OpenAI Configuration
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Define a system prompt for the chatbot
SYSTEM_PROMPT = "Act as an auction and vehicle history expert, proficient in platforms, repairs, and title processes. Users may provide car details from Carfax platform to get the most aproximate estimate of a car value for optimizing bidding in auction sales. Bear in mind that if the user request the processing of a PDF this data is available to you via our own conversion process and your answer should be affirmative."


engine = create_engine('sqlite:///carfaxbot.db')
Session = sessionmaker(bind=engine)
session = Session()
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

        if questions[qorder]['type'] == 'options':
            keyboard = [questions[qorder]['options']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            await update.message.reply_text(questions[qorder]['question'], reply_markup=reply_markup)
        elif questions[qorder]['type'] == 'open':
            await context.bot.send_message(chat_id=chat_id, text=questions[qorder]['question'])
        Conversations.add_answer_message(active_conversation.conversation_id,questions[qorder]['question'],"",qorder)
       

    elif len(current_context_messages) == len(questions.keys()):
        previous_question = current_context_messages[-1]
        previous_answer   = user_message
        Conversations.set_question_property(previous_question.id,"answer",previous_answer)
        Conversations.finish_conversation(active_conversation.conversation_id)           # Finalizar la conversación cuando tenga todoss los datos
        
    else:
        previous_question = current_context_messages[-1]
        previous_answer   = user_message

        if previous_answer != "/calcular_fees": #prevents from saving the accidental command repetition
            Conversations.set_question_property(previous_question.id,"answer",previous_answer)

        if not previous_question.answer or previous_question.answer == '':
            qorder  = previous_question.qorder
        else:
            qorder = previous_question.qorder + 1

        if questions[qorder]['type'] == 'options':
            keyboard = [questions[qorder]['options']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            await update.message.reply_text(questions[qorder]['question'], reply_markup=reply_markup)
        elif questions[qorder]['type'] == 'open':
            await context.bot.send_message(chat_id=chat_id, text=questions[qorder]['question'])
        Conversations.add_answer_message(active_conversation.conversation_id,questions[qorder]['question'],"",qorder)
        # await context.bot.send_message(chat_id=chat_id, text=questions[qorder]['question'])
    


    Conversations.set_chat_property(chat_id,'last_interaction',datetime.now() )
    if active_conversation.finished == True:
        # force Update chat state and datetime 
        Conversations.set_chat_property(chat_id,'current_chat_mode','message')

        carfees = []
        estimate = float(current_context_messages[2].answer)
        carfees.append(estimate)
        titletype = current_context_messages[0].answer
        vehicletype = current_context_messages[1].answer
        paymenttype = 'Secure'
        platformfee = session.query(CarFee).filter(CarFee.FinalBidMin<= estimate, CarFee.FinalBidMax>= estimate , CarFee.TitleType == titletype,CarFee.VehicleType == vehicletype , CarFee.PaymentType == paymenttype).first()
        platformfee = float(platformfee.Fee)
        carfees.append(platformfee)

        total_amount = np.asarray(carfees).sum()

        output="""
*Costo final estimado*

${}

`Este es solo un estimado y no el costo final.`
   
*Cost Breakdown*

    _Bid Amount_ : ${} 
    _Buyer Fee_  : ${}
    
     """.format(total_amount,estimate,platformfee)
        await context.bot.send_message(chat_id=chat_id,text=output,parse_mode='Markdown')
#     """ | Gate Fee          | $79.00    |
#  | Internet Bid Fee  | $119.00   |
#  | Enviromental Fee  | $10.00    |
#  | Title Mailing Fee | $20.00    |
#  | Mapa Broker Fee   | $550.00   |"""





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
