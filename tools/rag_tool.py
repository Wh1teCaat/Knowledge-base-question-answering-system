import os
import sys

import yaml
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from tools.base_tool import BaseToolWrapper

current_script_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_script_path))
os.chdir(project_root)
sys.path.append(project_root)

config_path = project_root/ "config.yaml"
with open(config_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
data_path = config["loader"]["data_path"]
cache_path = config["embedding"]["cache_path"]
db_path = config["retriever"]["db_path"]


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
            response = retriever.invoke(query)
            return response

        return StructuredTool.from_function(
            func=_rag_func,
            name=self.name,
            description=self.description,
            arg_schema=ArgSchema,
            return_direct=False
        )


rag_retriever = RagTool(data_path, db_path, cache_path).build()
