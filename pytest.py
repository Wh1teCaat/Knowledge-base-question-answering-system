import sys
import asyncio
from agent import Agent

if sys.platform.startswith('win32'):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    agent = await Agent.create()
    res = await agent.ainvoke("生成一篇800字作文，选题任意",  "user_a")
    print(res.answer)
    res = await agent.ainvoke("2025.12.1武汉天气", "user_b")
    print(res.answer)
    res = await agent.ainvoke("刚刚问了什么问题", "user_a")
    print(res.answer)
    res = await agent.ainvoke("刚刚问了什么问题", "user_b")
    print(res.answer)

    await agent.aclose()

if __name__ == '__main__':
    asyncio.run(main())