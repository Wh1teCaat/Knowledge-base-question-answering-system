# 需要先安装: pip install langchain-core
from langserve import RemoteRunnable
from langchain_core.messages import HumanMessage

remote_chain = RemoteRunnable("http://localhost:8000/agent")

# 1. 直接调用 (Invoke)
# "input" 的内容取决于你定义的 AgentInputSchema，通常是字典或字符串
response = remote_chain.invoke({
    "messages": [HumanMessage(content="你是谁？")],
})
print(response)
