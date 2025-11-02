from langchain_core.tools import StructuredTool
from tools.base_tool import BaseToolWrapper
from pydantic import BaseModel, Field


class RagTool(BaseToolWrapper):
    DEFAULT_NAME = "RagTool"
    DEFAULT_DESC = "可以根据用户提问从本地向量数据库中检索数据"

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
            response = retriever.invoke(query)
            return "\n".join([doc.page_content for doc in response])

        return StructuredTool.from_function(
            func=_rag_func,
            name=self.name,
            description=self.description,
            arg_schema=ArgSchema,
            return_direct=False
        )