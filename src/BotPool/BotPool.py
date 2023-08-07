import websockets
import asyncio 
import uuid
import json 
from functools import partial
import atexit
import logging

SERVER_URL = "ws://botted.gay"


UUID_To_Bots = {}


def NewAccount(Body):
    BotUUID = Body["UUID"]
    UserId = Body["UserId"]
    Bot = UUID_To_Bots[BotUUID]

    Bot.UserId = UserId

def BotJoined(Body):
    Username = Body["Username"]
    UserId = Body["UserId"]
    
    BotUUID = Body["UUID"]

    BotObject = UUID_To_Bots[BotUUID]

    BotObject.Name = Username 
    BotObject.UserId = UserId

    BotObject.Joined = True


def RefreshUUID(Body):
    global UUID_To_Bots
    OldUUIDs = Body["OldUUIDs"]
    NewUUIDs = Body["NewUUIDs"]

    for i in range(0, len(OldUUIDs)):
        Old = OldUUIDs[i]
        New = NewUUIDs[i]

        BotObject = UUID_To_Bots[Old]

        BotObject.UUID = New

        UUID_To_Bots[Old] = None
        UUID_To_Bots[New] = BotObject


Interceptions = {
    "NewAccount": NewAccount,
    "BotJoined": BotJoined,
    "RefreshUUID": RefreshUUID,

}

class Connection:
    def __init__(self, **kwargs):
        host = kwargs.get('host')
        Interceptions = kwargs.get('interceptions')
        API_KEY = kwargs.get('api_key')

        self.OutgoingMessages = {}   
        self.Interceptions = Interceptions
        self.API_KEY = API_KEY
        self.host = host

        self.Websocket = None  


    async def initialize_connection(self):
        self.Websocket = await websockets.connect(self.host)
        


    async def handle_websocket_messages(self):
        websocket = self.Websocket
        while True:
            message = await websocket.recv()
            try:
                message = json.loads(message)
                MessageId = message.get("MessageId")
                Body = message.get("Body")
                Operation = message.get("Operation")

                if MessageId:
                    self.OutgoingMessages[MessageId] = Body
                else:
                    self.__handle_interceptions(Operation, Body)
            except json.JSONDecodeError:
                logging.error(message)

            
    
    def __handle_interceptions(self, Operation, Body):
        self.Interceptions[Operation](Body)
    
    async def AskServerTwoWay(self, Operation, Data = {}):
        OutgoingMessages = self.OutgoingMessages

        UUID = str(uuid.uuid4())
        Data["MessageId"] = UUID
        await self.SendServer(Operation, Data)

        while not OutgoingMessages.get(UUID):
            await asyncio.sleep(0.1)
        
        Response = OutgoingMessages[UUID]
        OutgoingMessages[UUID] = None

        return Response

    async def SendServer(self, Operation, data = {}):
        Payload = json.dumps({
            "Operation": Operation,
            "Arguments": data,
            "API_KEY" : self.API_KEY
        })
        await self.Websocket.send(Payload)


class Bot:
    def __init__(self, Connection, **kwargs):
        global UUID_To_Bots

        OPERATION_METHODS = [
            "Chat",
            "Tell",
            "Disconnect",
            "SetMemory",
        ]

        self.UUID = kwargs["UUID"]
        self.Connection = Connection

        self.PlaceId = None
        self.Name = None
        self.UserId = None
        self.JobId = None
        self.Joined = False

        UUID_To_Bots[self.UUID] = self

        for Operation in OPERATION_METHODS:
            method = partial(self.__create_dynamic_method, Operation=Operation)
            setattr(self, Operation, method)
    

    async def __create_dynamic_method(self, Operation, Data=None):
        await self.Connection.SendServer("operate", {
            "BotOperation": Operation,
            "BotUUID": self.UUID,
            "Body" : Data
        })

    async def WaitForJoin(self):
        while not self.Joined:
            await asyncio.sleep(0.1)

    async def Execute(self, Code):
        return await self.Connection.AskServerTwoWay("operate", {
            "BotOperation" : "Execute",
            "BotUUID": self.UUID,
            "Body": Code,
        })

    async def GetMemory(self, Key):
        return self.Connection.AskServerTwoWay("operate", {
            "BotOperation" : "GetMemory",
            "BotUUID": self.UUID,
            "Body": Key,
        })["Value"]

    async def Launch(self, **kwargs):
        PlaceId = kwargs["PlaceId"]
        JobId = kwargs["JobId"]

        self.PlaceId = PlaceId
        self.JobId = JobId

        await self.Connection.SendServer("operate", {
            "BotOperation": "Launch",
            "BotUUID": self.UUID,
            "Body": { 
                "PlaceId" : PlaceId,
                "JobId": JobId
            }
        })



class BotPool:
    def __init__(self, **kwargs):
        API_KEY = kwargs["API_KEY"]
        self.Inited = False
        self.Connection = Connection(host = SERVER_URL + "/api/interface", interceptions = Interceptions, api_key = API_KEY)
    
    async def init(self):
        await self.Connection.initialize_connection()
        asyncio.create_task(self.Connection.handle_websocket_messages())
        asyncio.create_task(self.__pinger())
        self.__handle_close()
        self.Inited = True
        
    async def Allocate(self, **kwargs):
        RequestedBotAmount = kwargs["RequestedBotAmount"]

        UUIDs = await self.Connection.AskServerTwoWay("allocate", {
            "RequestedBotAmount": RequestedBotAmount,
        })

        Pool = [Bot(self.Connection, UUID = UUID) for UUID in UUIDs]
        self.Pool = Pool

        return Pool


    def __handle_close(self):
        def deallocate():
            for Bot in self.Pool:
                Bot.Disconnect()
            self.Connection.SendServer("deallocate")
            self.Connection.Websocket.close()
        atexit.register(deallocate)

    async def __pinger(self):
        while True:
            await self.Connection.SendServer("Ping")
            await asyncio.sleep(7)

    async def GetAccountStatus(self):
        if not self.Inited:
            logging.error("Bot Pool is not initialized")
        return await self.Connection.AskServerTwoWay("AccountStatus")

    async def GetPoolStatus(self):
        if not self.Inited:
            logging.error("Bot Pool is not initialized")
        return await self.Connection.AskServerTwoWay("PoolStatus")
