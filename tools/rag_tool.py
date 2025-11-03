from langchain_core.tools import StructuredTool
from tools.base_tool import BaseToolWrapper
from pydantic import BaseModel, Field


class RagTool(BaseToolWrapper):
    DEFAULT_NAME = "RagTool"
    DEFAULT_DESC = """
    当用户的问题需要查找知识库中具体信息（例如论文、技术内容、事实说明等）时使用此工具。
    仅当问题属于“知识问答、专业内容、事实查询”时调用；
    对于闲聊、反问、总结、情绪、历史对话类问题，请直接回答，不要调用本工具。
    """

    def __init__(self, data_path, db_path, cache_path):
        super().__init__()
        self.data_path = data_path
        self.db_path = db_path
        self.cache_path = cache_path

    def build(self):
        from retriever import RAG
        rag = RAG(self.data_path, self.db_path, self.cache_path)
        retriever = rag.get_retriever()

        class ArgSchema(BaseModel):
            query: str = Field(description="用户输入内容")

        def _rag_func(query: str):
            if isinstance(query, bytes):
                query = query.decode('utf-8', errors='ignore')
            else:
                try:
                    # 部分版本LangChain会把中文经过ISO-8859-1再转utf8
                    query = query.encode('latin1').decode('utf-8')
                except:
                    pass
            print(f"🧩 [RagTool] 实际接收到的 query: {repr(query)}")
            response = retriever.invoke(query)
            return "\n".join([doc.page_content for doc in response])

        return StructuredTool.from_function(
            func=_rag_func,
            name=self.name,
            description=self.description,
            arg_schema=ArgSchema,
            return_direct=False
        )
