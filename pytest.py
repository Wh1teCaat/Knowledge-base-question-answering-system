from agent import RAGAgent

agent = RAGAgent()
res = agent.invoke("生成一篇800字作文",  "user_a")
print(res)
res = agent.invoke("2025.11.8武汉天气", "user_b")
print(res)
res = agent.invoke("刚刚我问了什么问题", "user_a")
print(res)
res = agent.invoke("刚刚我问了什么问题", "user_b")
print(res)
