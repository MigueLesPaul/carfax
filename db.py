from sqlalchemy import Column, Integer, String,DECIMAL,create_engine
from sqlalchemy.orm import declarative_base,sessionmaker
import pandas as pd

Base = declarative_base()

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
    engine = create_engine('sqlite:///fees.db')  # You can change the database URL as needed
    Base.metadata.create_all(engine)  # Create the table
    Session = sessionmaker(bind=engine)
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


if __name__=="__main__":
    import_data()

    