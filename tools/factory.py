
from tools.tavily_tool import TavilyTool
from tools.rag_tool import RagTool
# from migration.tools.cal_tool import CalculatorTool
from pathlib import Path
import yaml


class ToolFactory:
    def __init__(self, **kwargs):
        """
        :param kwargs:
            enable_tavily: default True
            enable_rag: default True
            enable_calculator: default True
        """
        self.enable_tavily = kwargs.get("enable_tavily", True)
        self.enable_rag = kwargs.get("enable_rag", True)
        # self.enable_calculator = kwargs.get("enable_calculator", True)

    @staticmethod
    def _load_config():
        current_path = Path(__file__).resolve()
        project_path = current_path.parent.parent
        config_path = project_path / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config

    def get_tools(self):
        tools = []
        if self.enable_tavily:
            tools.append(TavilyTool().build())
        if self.enable_rag:
            config = self._load_config()
            data_path = config["loader"]["data_path"]
            db_path = config["retriever"]["db_path"]
            cache_path = config["embedding"]["cache_path"]
            tools.append(RagTool(data_path, db_path, cache_path).build())
        # if self.enable_calculator:
        #     tools.append(CalculatorTool().build())
        return tools


current_path = Path(__file__).resolve()
print(Path(__file__).resolve())
print(current_path.parent.parent)