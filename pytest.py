from agent import Agent

agent = Agent()
res = agent.invoke("生成一篇800字作文，选题任意",  "user_a")
print(res.answer)
res = agent.invoke("2025.12.1武汉天气", "user_b")
print(res.answer)
res = agent.invoke("刚刚问了什么问题", "user_a")
print(res.answer)
res = agent.invoke("刚刚问了什么问题", "user_b")
print(res.answer)
