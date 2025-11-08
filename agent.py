from multiusermemory import SummaryInjectMemory
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory

from tools.factory import ToolFactory
from langchain_openai import ChatOpenAI
import dotenv
import os

dotenv.load_dotenv()


class RAGAgent:
    def __init__(self):
        # 降低 temperature 以减少随机性，使相同问题得到更一致的答案
        # 0.1 在保持一定创造性的同时，减少随机性
        self.llm = ChatOpenAI(model=os.getenv("MODEL_NAME"), temperature=0.1)
        self.tools = ToolFactory().get_tools()
        self.store = {}
        
        # 使用 create_tool_calling_agent，更适合流式输出
        # 它使用函数调用而不是文本格式的 ReAct 模式，输出更清晰
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个智能问答助手。请根据用户的问题，使用可用的工具来获取信息，然后给出准确、详细的回答。
            规则：
            - 如果问题需要外部知识或事实检索，使用工具获取信息
            - 如果问题是一般性对话或思考，直接回答，不需要使用工具
            - 回答要准确、详细、有条理"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        self.agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=6
        )
        self.runnable = RunnableWithMessageHistory(
            runnable=self.executor,
            get_session_history=self.get_or_create_memory,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    def get_or_create_memory(self, session_id: str):
        if session_id not in self.store:
            self.store[session_id] = SummaryInjectMemory(
                llm=self.llm,
                max_token_limit=500,
                memory_key="chat_history",
                return_messages=True
            )
        return self.store[session_id]

    # class _MemoryExecutor:
    #     def __init__(self, parent):
    #         self.parent = parent
    #         self.runnable = parent.runnable
    #
    #     def invoke(self, inputs, config):
    #         session_id = config.get("configurable").get("session_id")
    #         if not session_id:
    #             raise ValueError("请在 config.configurable.session_id 中提供会话ID")
    #
    #         result = self.runnable.invoke(inputs, config=config)
    #         memory = self.parent.get_or_create_memory(session_id)
    #         memory.save_context(
    #             inputs={"human": inputs.get("input")},
    #             outputs={"ai": result.get("output")}
    #         )
    #         return result

    def get_memory_runnable(self):
        return self.runnable
