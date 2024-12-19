import openai
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup,ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, filters, CallbackContext,Application,ApplicationBuilder, CallbackQueryHandler
from dotenv import load_dotenv
import os
from db import CarFee,ConversationManager,Message
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine,func
from datetime import datetime 
import yaml
import numpy as np
import pdfplumber
from io import BytesIO

load_dotenv()
# Set your API keys
OPENAI_API_KEY = os.getenv("OPENAI_CHAT_GPT_KEY") 
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_API_TOKEN")


# OpenAI Configuration
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Define a system prompt for the chatbot
SYSTEM_PROMPT = """
Act as an auction and vehicle history expert, proficient in platforms, repairs, and title processes. 
This GPT is an expert on vehicle auctions and related processes. It knows everything about the platforms Copart, IAA, and Manheim, and is proficient in navigating and utilizing these websites to find vehicles, understand listings, and make recommendations. Additionally, it can analyze Carfax reports with precision, offering detailed insights into both the positive and negative aspects of any vehicle history presented.

The GPT is highly skilled at finding parts for vehicles by searching online and locally across the U.S., providing accurate repair cost estimates based on current pricing trends. It can also recommend the best deals on parts and direct users to the appropriate stores or websites for purchasing.

The GPT is familiar with towing services, able to find the best rates for transportation across the U.S., and recommend where users can find affordable options for moving vehicles.

It can go beyond Carfax and use other tools like BidCars or BidFax to uncover detailed vehicle histories, including previous sales or accidents. The GPT also knows the full process of buying and selling vehicles, advising on steps like title transfers, taxes, and any other legal documentation required.

Additionally, it understands the process for changing a vehicle’s title from salvage to rebuilt, providing guidance on every step of that transition.

This GPT also knows all the fees associated with Copart, and understands your service's broker fees: $297 for vehicles ranging from $0 to $6,999, $497 for vehicles from $7,000 to $15,000, and $597 for vehicles above $15,000.
Users may provide car details from Carfax platform to get the most aproximate estimate of a car value for optimizing bidding in auction sales.
Bear in mind that if the user request the processing of a PDF this data is available to you via our own conversion process and your answer should be affirmative. 
If the user ask for an estimation of the final price you should answer with a direct numeric value for the estimation and  redirect them to this custom command: /fees for the final estimation breakdown.

"""


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
    msg1 = Message(content=user_message,chat_id=chat_id,role="user")
    session.add(msg1)
    session.commit()
    # Extract the bot's reply
    bot_reply = response.choices[0].message.content
    # bot_reply="Que volá, te gusta que te responda?"
    print("""Bot: {}""".format(bot_reply))
    msg2 = Message(content=bot_reply,chat_id=chat_id,role="assistant")
    session.add(msg2)
    session.commit()
    # Send the reply back to the user on Telegram
    

    await context.bot.send_message(chat_id=chat_id, text=bot_reply,parse_mode="Markdown")



async def fee_calculator(update: Update, context: CallbackContext):
    """
    estimate: the estimated value to be paid
    output: text with a table including all the fees. 
    
    """
    if update.message:
        user_message = update.message.text
    else:
        user_message =""
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
        qtext = await translate(chat_id,questions[qorder]['question'])
        if questions[qorder]['type'] == 'options':
            keyboard = [questions[qorder]['options']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            await update.message.reply_text(qtext, reply_markup=reply_markup)
        elif questions[qorder]['type'] == 'open':
            await context.bot.send_message(chat_id=chat_id, text=qtext)
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

        if not previous_question.answer or previous_question.answer == '':    # prevent voided answers by questioning again
            qorder  = previous_question.qorder
        else:
            qorder = previous_question.qorder + 1

        qtext = await translate(chat_id,questions[qorder]['question'])
        if questions[qorder]['type'] == 'options':
            keyboard = [questions[qorder]['options']]
            reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
            await update.message.reply_text(qtext, reply_markup=reply_markup)
        elif questions[qorder]['type'] == 'open':
            await context.bot.send_message(chat_id=chat_id, text=qtext)
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

        maxvalue = session.query(func.max(CarFee.FinalBidMin)).filter().scalar()
        if estimate >= maxvalue:
            platformfee = session.query(CarFee).filter(CarFee.FinalBidMin<= estimate, CarFee.TitleType == titletype,CarFee.VehicleType == vehicletype , CarFee.PaymentType == paymenttype).order_by(CarFee.FinalBidMin.desc()).first()
        else:
            platformfee = session.query(CarFee).filter(CarFee.FinalBidMin<= estimate, CarFee.FinalBidMax>= estimate , CarFee.TitleType == titletype,CarFee.VehicleType == vehicletype , CarFee.PaymentType == paymenttype).first()
        
        if platformfee.FeeType == 'Absolute':
            platformfee = float(platformfee.Fee)
        elif platformfee.FeeType == 'Percentual':
            platformfee = (float(platformfee.Fee)/100.0 )*estimate 

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
        output = await translate(chat_id,output)
        output = output.split(';')[-1]
        reply_markup = await default_buttons(update)
        await context.bot.send_message(chat_id=chat_id,text=output,parse_mode='Markdown',reply_markup=reply_markup)
        
#     """ | Gate Fee          | $79.00    |
#  | Internet Bid Fee  | $119.00   |
#  | Enviromental Fee  | $10.00    |
#  | Title Mailing Fee | $20.00    |
#  | Mapa Broker Fee   | $550.00   |"""


async def handle_document(update: Update, context: CallbackContext):
    document = update.message.document
    chat_id = update.message.chat_id
    file = await document.get_file()
    file_stream = BytesIO()
    file= await file.download_to_memory(file_stream)
    file_stream.seek(0)

    info_text= await translate(chat_id,"Ok. Revisaré esa información para ti.")

    await context.bot.send_message(chat_id=chat_id, text=info_text)

    with pdfplumber.open(file_stream) as pdf:
        text = """
        Can you help me get an optimized estimate of an amount of money safe to bid for a car based on the following Carfax history information:
            

    
         """
        for p in pdf.pages:
            text+=p.extract_text()
    
    response = client.chat.completions.create(
    model="gpt-4", #"gpt-3.5-turbo",     #  # or "gpt-3.5-turbo"
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text}]
    )
    print("""User: {}""".format(text))
    msg1 = Message(content=info_text,chat_id=chat_id,role="user")
    session.add(msg1)
    session.commit()
    # Extract the bot's reply
    bot_reply = response.choices[0].message.content
    # bot_reply="Que volá, te gusta que te responda?"
    print("""Bot: {}""".format(bot_reply))
    # Send the reply back to the user on Telegram
    msg1 = Message(content=bot_reply,chat_id=chat_id,role="assistant")
    session.add(msg1)
    session.commit()
    reply_markup = await default_buttons(update)
    await context.bot.send_message(chat_id=chat_id, text=bot_reply,reply_markup=reply_markup)


async def translate(chat_id,phrase):
    """
    provide a chat_id to check the last user messages and translate the phrase to the detected language
     """
    user_message = Conversations.get_previus_user_messages(chat_id=chat_id)[-1]     # get the previous message

    return await utranslator(user_message,phrase)

async def utranslator(target,phrase):
    initial_prompt = """You will act as an expert multilingual translator. 
    I will provide you with a phrase to identify what language is written in and another phrase to be translated. 
    You must ALWAYS answer only with the second phrase translated to the identified language and anything else.
    If the language of both phrases is the same you will keep the second one verbatim
    The phrases will be separated by a semicolon.
    """
    text = " ; ".join([target,phrase])
    response = client.chat.completions.create(
    model="gpt-4", #"gpt-3.5-turbo",     #  # or "gpt-3.5-turbo"
    messages=[
        {"role": "system", "content": initial_prompt},
        {"role": "user", "content": text}]
    )
    return response.choices[0].message.content


async def finish_conversation(conversation_id):
    Conversations.finish_conversation(conversation_id)
async def create_new_answer_message(conversation_id,question,answer,qorder):
    Conversations.add_answer_message(conversation_id,question,answer,qorder)

def is_numeric(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

async def start_handler(update: Update,context: CallbackContext):
    chat_id = update.message.chat_id
    welcome_message = """
*Asistente JM Broker*

¡Hola! Soy tu experto en subastas e historial de vehículos, competente en plataformas, reparaciones y procesos de títulos.

_Creado por Héctor González_

    """
    # welcome_message = await translate(chat_id,welcome_message)
    # await context.bot.send_message(chat_id=chat_id,text = welcome_message,parse_mode='Markdown')
    active_conversation_list = Conversations.get_unfinished_conversations(chat_id)
    for ac in active_conversation_list:
        await finish_conversation(ac.conversation_id)
    reply_markup = await default_buttons(update)
    await context.bot.send_message(chat_id=chat_id,text=welcome_message,parse_mode="Markdown",reply_markup=reply_markup)
    



async def default_buttons(update):
    keyboard = [[
        "¿Cómo analizo este informe de Carfax en busca de problemas?",
        "Ayúdame a encontrar las mejores ofertas en Copart, IAA o Manheim."],
        ["¿Dónde puedo encontrar las piezas más baratas para una reparación de automóvil?",
       "¿Cuál es el proceso para convertir un título salvage a un título rebuilt?"],
        ["/fee calculator"]
        ]

    # keyboard = [[InlineKeyboardButton("Calcular Fees", callback_data='/fees')]]

    reply_markup = ReplyKeyboardMarkup(keyboard)
    # reply_markup = InlineKeyboardMarkup(keyboard)
    return reply_markup


async def button_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    if query.data == '/fees':
        await fee_calculator(update,context)



# Start the Telegram bot
def main():
    application=(
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    application.add_handler(CommandHandler("start",start_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle_message))
    application.add_handler(CommandHandler("calcular_fees",fee_calculator))
    application.add_handler(CommandHandler("fees",fee_calculator))
    application.add_handler(CommandHandler("fee",fee_calculator))
    
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(CallbackQueryHandler(button_callback_handler))
    application.run_polling()
if __name__ == "__main__":
    main()
