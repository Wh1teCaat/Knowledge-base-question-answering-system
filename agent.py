from langchain.memory import ConversationSummaryBufferMemory
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableWithMessageHistory

from tools.factory import ToolFactory
from langchain_openai import ChatOpenAI
import dotenv
import os

dotenv.load_dotenv()


class RAGAgent:
    template = """
    Answer the following questions as best you can. You have access to the following tools:

    {tools}

    You must always use the following format exactly:

    Question: the input question you must answer
    Thought: your reasoning about what to do next
    Action: the action to take, must be one of [{tool_names}]
    Action Input: the input to the action
    Observation: the result of the action
    (Repeat Thought/Action/Action Input/Observation as needed)
    Thought: I now know the final answer
    Final Answer: your final answer to the question

    Rules:
    - You must always use the exact English keywords 
        ("Question", "Thought", "Action", "Action Input", "Observation", "Final Answer").
    - If you are not sure which action to take, do NOT output 'Action:' or 'Action Input:'.
    - Instead, go directly to the "Final Answer".
    - If the question is about general conversation or reflection, answer directly without using tools.
    - Only use tools when external factual or knowledge retrieval is required.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", template),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("ai", "{agent_scratchpad}"),
    ])

    def __init__(self):
        self.llm = ChatOpenAI(model=os.getenv("MODEL_NAME"), temperature=0.1)
        self.tools = ToolFactory().get_tools()
        self.store = {}
        self.agent = create_react_agent(
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
            get_session_history=self.get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    def get_or_create_memory(self, session_id: str):
        if session_id not in self.store:
            self.store[session_id] = ConversationSummaryBufferMemory(
                llm=self.llm,
                max_token_limit=500,
                memory_key="chat_history",
                return_messages=True
            )
        return self.store[session_id]

    def get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        return self.get_or_create_memory(session_id).chat_memory

    class _MemoryExecutor:
        def __init__(self, parent):
            self.parent = parent
            self.runnable = parent.runnable

        def invoke(self, inputs, config):
            session_id = config.get("configurable").get("session_id")
            if not session_id:
                raise ValueError("请在 config.configurable.session_id 中提供会话ID")

            result = self.runnable.invoke(inputs, config=config)
            memory = self.parent.get_or_create_memory(session_id)
            memory.save_context(
                inputs={"human": inputs.get("input")},
                outputs={"ai": result.get("output")}
            )
            return result

    def get_memory_runnable(self):
        return self._MemoryExecutor(self)
