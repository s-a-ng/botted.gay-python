## Installation
```
pip install git+https://github.com/s-a-ng/botted.gay-python.git
```
## Usage
```py
import botteddotgay as BotPool
import asyncio

async def main():
    BotPoolObject =  BotPool(
        API_KEY = "BOTTED-GAY-yertyertretertghxhgfhherhrythtyjnteyjytjn"
    )

    await BotPoolObject.init()

    Bots = await BotPoolObject.Allocate(
        RequestedBotAmount = 20
    )

    for Bot in Bots:
        await Bot.Launch(
            PlaceId = 1010,
            JobId = ""
        )

    for Bot in Bots:
        await Bot.WaitForJoin()

    for Bot in Bots:
        await Bot.Chat("hi")

    await asyncio.sleep(5)

    for Bot in Bots:
        await Bot.Disconnect()

asyncio.run(main())
```
