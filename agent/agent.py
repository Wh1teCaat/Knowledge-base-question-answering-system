import os
from typing import TypedDict, Annotated, Optional

import dotenv
import tiktoken
from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from RAGAgent import call_rag_expert
from SearchAgent import call_search_expert

dotenv.load_dotenv()


class Receipt(BaseModel):
    """结构化输出"""
    reason: str = Field(
        default=None,
        description="""
        【思维链分析】
        1. 用户最新一句话的意图是什么？（是延续上文，还是开启新任务？）
        2. 如果需要回忆，请提取历史消息中的关键信息。
        3. 解释为什么选择调用（或不调用）某个工具。
        """
    )
    answer: str = Field(
        description="""
        针对用户问题的最终回答内容。
        【重要警告】：
        - 如果用户要求写作文、写代码、写长文，此字段**必须包含完整的生成内容（全文）**。
        - **严禁**只输出一句“已生成作文”或“见下文”之类的摘要。
        - 必须是用户想看的那个结果本身。
        """
    )
    source: list[str] = Field(description="回答中引用的具体文档名称或页码列表。如果没用到文档，请留空。")


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    summary: Optional[str]
    structured_answer: Optional[Receipt]


class Agent:
    def __init__(self, runnable, pool):
        self.runnable = runnable
        self.pool = pool

    @classmethod
    async def create(cls, max_tokens=5000):
        max_tokens = max_tokens
        tools = [call_rag_expert, call_search_expert]
        tools_by_name = {tool.name: tool for tool in tools}
        llm = ChatOpenAI(model=os.getenv("MODEL_NAME"))
        llm_with_tools = llm.bind_tools(tools)
        llm_structured = llm.with_structured_output(Receipt)

        async def _structured_node(state: AgentState):
            messages = state["messages"]
            summary = state.get("summary", "")

            if summary:
                prompt_msg = [SystemMessage(content=f"上下文摘要：{summary}")] + messages
            else:
                prompt_msg = messages

            receipt = await llm_structured.ainvoke(prompt_msg)
            return {"structured_answer": receipt}

        async def _summary_node(state: AgentState):
            """摘要逻辑节点"""
            messages = state['messages']
            existing_summary = state.get("summary", "")

            # 计算当前消息 token 数
            encoding = tiktoken.encoding_for_model("gpt-4o-mini")
            total_tokens = 0
            for msg in messages:
                content = msg.content if isinstance(msg.content, str) else ""
                total_tokens += len(encoding.encode(content))

            if total_tokens < max_tokens:
                return {}

            tokens = 0
            cut_index = 0
            for i, msg in enumerate(messages):
                content = msg.content if isinstance(msg.content, str) else ""
                tokens += len(encoding.encode(content))
                # 删减后的 token 满足限制
                if total_tokens - tokens < max_tokens:
                    cut_index = i + 1
                    break

            if cut_index < len(messages):
                first_kept_msg = messages[cut_index]
                if isinstance(first_kept_msg, ToolMessage):
                    cut_index += 1

            summary_msg = messages[:cut_index]
            delete_msg = [RemoveMessage(id=msg.id) for msg in summary_msg]

            summary_prompt = (
                "请将上面的对话内容总结为一个摘要。"
                f"现有的摘要：{existing_summary}"
            )
            summary_message = await llm.ainvoke(
                summary_msg + [HumanMessage(content=summary_prompt)],
                )
            new_summary = summary_message.content

            return {
                "messages": delete_msg,
                "summary": new_summary,
            }

        async def _agent_node(state: AgentState):
            messages = state["messages"]
            summary = state.get("summary", "")

            system_prompt = """你是一个高智能对话系统的**任务调度与决策中枢 (Central Orchestrator)**。

            【角色定位】
            你拥有多种专业工具的调用权限。你的核心职责不是机械地回复，而是作为**大脑**，分析用户意图，精准调度工具或调取记忆来解决问题。

            【核心原则：最新指令优先 (Priority on Latest Instruction)】
            在多轮对话中，用户意图经常会发生漂移（Intent Drift）。你必须严格遵守以下规则：
            1. **锚定当下**：无论之前的对话上下文多么长（如长篇写作、代码生成），你必须**优先响应用户最新发送的一条指令**。
            2. **打破惯性 (Break Context Inertia)**：
               - 严禁被上文的格式带偏。如果上文是写作文，而用户最新问“几点了”，立即切换回简短回答模式，**绝对不要**再写一篇作文。
               - 严禁在用户询问“回顾历史”时生成新内容。

            【决策逻辑与资源调度】
            请根据用户最新指令的性质，选择唯一的处理路径：
            - **路径 A：需要外部能力**（如事实查询、计算、实时信息）
              ➜ 必须调用对应的 **Tools**，严禁凭空猜测。
            - **路径 B：需要回顾历史**（如“我刚才说什么了”、“总结上文”）
              ➜ 调取 **对话历史 (Messages)** 或 **摘要 (Summary)** 进行事实复述。
            - **路径 C：纯逻辑/闲聊**（如打招呼、通用问答）
              ➜ 直接利用自身能力简练回复。

            【思维链 (Reasoning) 协议】
            在输出最终结果前，必须在 `reason` 字段中执行隐式推理：
            1. **意图判别**：用户的最新意图属于上述哪种路径（A/B/C）？
            2. **上下文清洗**：确认是否需要忽略上文的干扰信息（如长文本）？
            3. **工具决策**：如果需要调用工具，理由是什么？
            
            【输出规范】
            1. **完整性原则**：如果用户要求生成长文本（作文、报告、代码），你必须生成用户需要的答案。
            2. **严禁偷懒**：不要因为是 JSON 格式就省略内容。

            请保持客观、冷静、服务型的对话风格。"""
            system_msg = [SystemMessage(content=system_prompt)]

            if summary:
                system_msg.append(SystemMessage(content=f"之前的对话摘要：{summary}"))

            messages = system_msg + messages

            result = await llm_with_tools.ainvoke(messages)
            return {"messages": [result]}

        async def _tool_node(state: AgentState):
            last_msg = state["messages"][-1]

            if not last_msg.tool_calls:
                return {}

            tool_msgs = []
            for tool_call in last_msg.tool_calls:
                name = tool_call["name"]
                if name not in tools_by_name:
                    output = f"Error: 调用不存在的工具"
                else:
                    try:
                        tool_func = tools_by_name[name]
                        args = tool_call["args"]
                        output = await tool_func.ainvoke(args)
                    except Exception as e:
                        output = f"Error: {e}"
                tool_msgs.append(
                    ToolMessage(
                        content=str(output),
                        tool_call_id=tool_call["id"]
                    )
                )
            return {"messages": tool_msgs}

        graph = StateGraph(AgentState)
        graph.add_node("summary", _summary_node)
        graph.add_node("agent", _agent_node)
        graph.add_node("tools", _tool_node)
        graph.add_node("formatter", _structured_node)
        graph.set_entry_point("summary")
        graph.add_edge("summary", "agent")
        graph.add_edge("tools", "agent")

        def agent_continue(state: AgentState):
            last_msg = state["messages"][-1]
            if last_msg.tool_calls:
                return "tools"
            else:
                return "formatter"

        graph.add_conditional_edges("agent", agent_continue)
        graph.add_edge("formatter", "__end__")

        # 建立 Postgres 连接池
        # 连接字符串格式: postgresql://用户名:密码@地址:端口/数据库名
        # 例如: postgresql://postgres:123456@localhost:5432/agent_db
        db_url = os.getenv("POSTGRES_URL")

        conn_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
        }

        pool = AsyncConnectionPool(
            conninfo=db_url,
            max_size=20,
            kwargs=conn_kwargs,
            open=False,
        )

        await pool.open()

        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()  # 第一次运行时，需要创建表结构

        compiled_graph = graph.compile(checkpointer=checkpointer)
        return cls(compiled_graph, pool)

    async def ainvoke(self, query: str, thread_id: str = None):
        """
        封装后的调用接口
        :param query: 用户的纯文本问题
        :param thread_id: 会话 ID，用于记忆隔离
        :return: 最终的结构化结果 (Receipt 对象) 或 错误信息
        """
        inputs = {"messages": [HumanMessage(content=query)]}
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None

        # 执行图
        final_state = await self.runnable.ainvoke(inputs, config=config)

        # 优先返回结构化答案，如果没有（比如出错了），返回最后一条文本消息
        if final_state.get("structured_answer"):
            return final_state["structured_answer"]
        else:
            return final_state["messages"][-1].content

    async def aclose(self):
        await self.pool.close()
