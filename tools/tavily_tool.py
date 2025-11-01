from langchain_community.tools import TavilySearchResults
from base_tool import BaseToolWrapper
import dotenv, os

dotenv.load_dotenv()


class TavilyTool(BaseToolWrapper):
    DEFAULT_NAME = "tavily_search"
    DEFAULT_DESC = "调用Tavily搜索引擎获取最新网页内容"

    def __init__(self, max_results=3):
        super().__init__()
        self.max_results = max_results

    def build(self):
        os.environ["TAVILY_API_KEY"] = os.getenv("TAVILY_API_KEY")
        return TavilySearchResults(max_results=self.max_results)
