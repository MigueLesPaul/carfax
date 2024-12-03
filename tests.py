from tgrm import utranslator,translate
import asyncio
 
async def test1(): 
    print( await utranslator("Auf Wiedersehen!","Hola, Como Puedo ayudarte?"))

async def test2():
    print(await translate(572031301,"Hello, How can I help you?"  ))
asyncio.run(test2())