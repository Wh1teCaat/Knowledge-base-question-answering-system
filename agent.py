from langchain.memory import ConversationSummaryBufferMemory
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain import hub
from tools.factory import ToolFactory
from langchain_ollama import ChatOllama
import dotenv
import os

dotenv.load_dotenv()


class RAGAgent:
    def __init__(self):
        self.llm = ChatOllama(model=os.getenv("OLLAMA_MODEL_NAME"))
        self.memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=500,
            memory_key="chat_history",
            return_messages=True
        )
        self.prompt = hub.pull("hwchase17/openai-functions-agent")
        self.tools = ToolFactory().get_tools()

    def get_executor(self):
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True
        )
        return agent_executor
