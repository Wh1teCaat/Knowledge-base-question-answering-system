import os
import sqlite3
from typing import TypedDict, Annotated, Optional

import dotenv
import tiktoken
from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from RAGAgent import call_rag_expert
from SearchAgent import call_search_expert

dotenv.load_dotenv()


class RAGAgent:
    def __init__(self, max_tokens=5000):
        class Receipt(BaseModel):
            """结构化输出"""
            reason: Optional[str] = Field(
                default=None,
                description="""
                仅在需要思考时，填写此字段；
                先分析用户的意图和检索到的文档内容，解释你为什么会得出后续的结论；
                如果问题非常简单（如问候、闲聊）或无需查阅文档，请忽略此字段（设为 None）。
                """
            )
            answer: str = Field(description="模型最终得到的答案，回答简洁、针对用户问题。")
            source: list[str] = Field(description="回答中引用的具体文档名称或页码列表。如果没用到文档，请留空。")

        class AgentState(TypedDict):
            messages: Annotated[list[BaseMessage], add_messages]
            summary: Optional[str]
            structured_answer: Optional[Receipt]

        self._max_tokens = max_tokens
        self._tools = [call_rag_expert, call_search_expert]
        self._tools_by_name = {tool.name: tool for tool in self._tools}
        self._llm = ChatOpenAI(model=os.getenv("MODEL_NAME"))
        self._llm_with_tools = self._llm.bind_tools(self._tools)
        self._llm_structured = self._llm.with_structured_output(Receipt)

        self._conn = sqlite3.connect("agent_db.sqlite", check_same_thread=False)
        self._checkpointer = SqliteSaver(conn=self._conn)

        def _structured_node(state: AgentState):
            messages = state["messages"]
            summary = state.get("summary", "")

            if summary:
                prompt_msg = [SystemMessage(content=f"上下文摘要：{summary}")] + messages
            else:
                prompt_msg = messages

            receipt = self._llm_structured.invoke(prompt_msg)
            return {"structured_answer": receipt}

        def _summary_node(state: AgentState):
            """摘要逻辑节点"""
            messages = state['messages']
            existing_summary = state.get("summary", "")

            # 计算当前消息 token 数
            encoding = tiktoken.encoding_for_model("gpt-4o-mini")
            total_tokens = 0
            for msg in messages:
                content = msg.content if isinstance(msg.content, str) else ""
                total_tokens += len(encoding.encode(content))

            if total_tokens < self._max_tokens:
                return {}

            tokens = 0
            cut_index = 0
            for i, msg in enumerate(messages):
                content = msg.content if isinstance(msg.content, str) else ""
                tokens += len(encoding.encode(content))
                # 删减后的 token 满足限制
                if total_tokens - tokens < self._max_tokens:
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
            summary_message = self._llm.invoke(
                summary_msg + [HumanMessage(content=summary_prompt)],
                )
            new_summary = summary_message.content

            return {
                "messages": delete_msg,
                "summary": new_summary,
            }

        def _agent_node(state: AgentState):
            messages = state["messages"]
            summary = state.get("summary", "")

            if summary:
                system_msg = SystemMessage(content=f"之前的对话摘要：{summary}")
                messages = [system_msg] + messages

            result = self._llm_with_tools.invoke(messages)
            return {"messages": [result]}

        def _tool_node(state: AgentState):
            last_msg = state["messages"][-1]

            if not last_msg.tool_calls:
                return {}

            tool_msgs = []
            for tool_call in last_msg.tool_calls:
                name = tool_call["name"]
                if name not in self._tools_by_name:
                    output = f"Error: 调用不存在的工具"
                else:
                    try:
                        tool_func = self._tools_by_name[name]
                        args = tool_call["args"]
                        output = tool_func.invoke(args)
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
        self.agent = graph.compile(checkpointer=self._checkpointer)

    def invoke(self, query: str, thread_id: str = None):
        """
        封装后的调用接口
        :param query: 用户的纯文本问题
        :param thread_id: 会话 ID，用于记忆隔离
        :return: 最终的结构化结果 (Receipt 对象) 或 错误信息
        """
        inputs = {"messages": [HumanMessage(content=query)]}

        # 自动构造配置 (简化调用)
        # 如果没传 thread_id，可以生成一个临时的，或者抛出错误
        config = {"configurable": {"thread_id": thread_id}} if thread_id else None

        # 执行图
        final_state = self.agent.invoke(inputs, config=config)

        # 优先返回结构化答案，如果没有（比如出错了），返回最后一条文本消息
        if final_state.get("structured_answer"):
            return final_state["structured_answer"]
        else:
            return final_state["messages"][-1].content
