from langchain.memory import ConversationSummaryBufferMemory
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate

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
    - You must always use the exact English keywords ("Question", "Thought", "Action", "Action Input", "Observation", "Final Answer").
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
        self.memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=500,
            memory_key="chat_history",
            return_messages=True
        )
        self.tools = ToolFactory().get_tools()

    def get_executor(self):
        agent = create_react_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=6
        )
        return agent_executor
