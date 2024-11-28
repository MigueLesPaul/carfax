from sqlalchemy import Column, Integer, String,DECIMAL,create_engine,Boolean,DateTime,ForeignKey
from sqlalchemy.orm import declarative_base,sessionmaker,relationship
import pandas as pd
import uuid
from datetime import datetime

Base = declarative_base()
engine = create_engine('sqlite:///carfaxbot.db')
Session = sessionmaker(bind=engine)

class CarFee(Base):
    __tablename__="carfees"
    id = Column(Integer, primary_key=True)
    FinalBidMin = Column(DECIMAL)
    FinalBidMax = Column(DECIMAL)
    Fee         = Column(DECIMAL)
    FeeType     = Column(String)     # Absolut or Percent
    TitleType   = Column(String)     # Salvage or Clean
    VehicleType = Column(String)      #  Standard or Heavy
    PaymentType = Column(String)      # Secured or un Secured 

def import_data():
    Base.metadata.create_all(engine)  # Create the table
    session = Session()

    df = pd.read_csv('Fees.csv')

    for index,row in df.iterrows():
        fee = CarFee(id=index,FinalBidMin=row['FinalBidMin'],
        FinalBidMax=row['FinalBidMax'],
        Fee = row['Fee'],
        FeeType=row['FeeType'],
        TitleType = row['TitleType'],
        VehicleType = row['VehicleType'],
        PaymentType = row['PaymentType']
        )

        session.add(fee)
        session.commit()
    session.close()

class Chat(Base):
    __tablename__="chats"    # chats identifies users. 
    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    username = Column(String)
    first_interaction = Column(DateTime,default=datetime.now())
    last_interaction = Column(DateTime,default=datetime.now())
    user_turn = Column(Boolean)
    bot_chat_process = Column(String)
    current_chat_mode = Column(String)           # command_name for commands, message for the rest (for handling with chatgpt)
    user_is_premium = Column(Boolean,default=False)
    conversation = relationship("Conversation", back_populates="chat")
   
    def to_dict(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}

class Conversation(Base):
    __tablename__="conversations"
    id = Column(Integer, primary_key=True)
    conversation_id=Column(String,default=lambda:str(uuid.uuid4()))
    start_time = Column(DateTime,default=datetime.now())
    end_time = Column(DateTime)
    chat_mode = Column(String)
    chat_id = Column(Integer, ForeignKey('chats.id'))
    finished = Column(Boolean,default=False)
    
    chat = relationship("Chat",back_populates="conversation")
    message = relationship("Message",back_populates="conversation")

class Message(Base):
    __tablename__="messages"
    id = Column(Integer, primary_key=True)
    content = Column(String)
    mtime  = Column(DateTime,default=datetime.now())
    conversation_id = Column(String,ForeignKey('conversations.conversation_id'))

    conversation = relationship("Conversation",back_populates="message")


class ConversationManager():
    def __init__(self):
        self.session = Session()
        self.qchats = self.session.query(Chat)

    
    def check_chat_in_db(self,chat_id):
        return bool(self.qchats.filter_by(chat_id=chat_id).first() )

    def add_chat(self,chat_id,current_chat_mode,username=""):
        self.session.add(Chat(chat_id=chat_id,current_chat_mode=current_chat_mode,username=username ))
        self.session.commit()

    def get_chat(self,chat_id):
        return self.qchats.filter_by(chat_id=chat_id).first().to_dict()

    def set_chat_property(self,chat_id,cproperty, cvalue):

        chat = self.qchats.filter_by(chat_id=chat_id).first()
        setattr(chat,cproperty,cvalue)
        self.session.commit()

        








if __name__=="__main__":
    import_data()

    