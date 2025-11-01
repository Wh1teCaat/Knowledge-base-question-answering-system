from base_tool import BaseToolWrapper
from langchain_experimental.tools.python.tool import PythonREPLTool


class CalculatorTool(BaseToolWrapper):
    DEFAULT_NAME = "Calculator"
    DEFAULT_DESC = "执行Python代码计算数学表达式"

    def __init__(self):
        super().__init__()

    def build(self):
        return PythonREPLTool()
