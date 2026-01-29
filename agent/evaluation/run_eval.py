import os
import sys
import uuid
from typing import Dict, Any

import dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import evaluate, Client
from pydantic import BaseModel, Field

from agent import RAGAgent

# 1. 获取当前脚本 (run_eval.py) 所在的绝对路径
current_script_path = os.path.abspath(__file__)
# 结果: D:\code\test_langchain\...\evaluation\run_eval.py

# 2. 获取项目根目录 (即 evaluation 的上一级)
project_root = os.path.dirname(os.path.dirname(current_script_path))
# 结果: D:\code\test_langchain\Knowledge-base-question-answering-system

# --- 关键修复代码 ---
# 3. 强制把当前的工作目录 (CWD) 切换到项目根目录
# 这样，你代码里所有的相对路径 (如 "./data", "./db") 都会基于根目录寻找
os.chdir(project_root)
print(f"🔄 已将工作目录切换至: {os.getcwd()}")

# 4. 把根目录加入 Python 搜索路径 (解决 import agent 报错)
sys.path.append(project_root)

dotenv.load_dotenv()
agent = RAGAgent()


class Comment(BaseModel):
    score: int = Field(
        description="对模型的回答进行打分，从0到100分，100为回复准确。",
        ge=0, le=100
    )
    comment: str = Field(
        description="对模型回答的简短评价。"
    )


def bridge_func(inputs: dict) -> dict:
    question = inputs["question"]
    thread_id = str(uuid.uuid4())   # 使用新会话，防止记忆影响

    result = agent.invoke(question, thread_id)
    if hasattr(result, "answer"):
        return {
            "reason": result.reason,
            "answer": result.answer,
            "source": getattr(result, "sources", ""),
        }
    else:
        return {
            "answer": str(result)
        }


llm = ChatGoogleGenerativeAI(model=os.getenv("GEMINI_MODEL"))
eval_llm = llm.with_structured_output(Comment)


def evaluator(run, example) -> Dict[str, Any]:

    """
    :param run: bridge_func 返回的结果
    :param example: 测试集示例及答案
    :return:
    """
    question = example.inputs.get("question")
    reference_answer = example.outputs.get("answer", "")
    outputs = getattr(run, "outputs", {}) or {}
    llm_answer = outputs.get("answer", "")

    prompt = f"""
    你是一个严格的评分员。
    
    问题：{question}
    标准答案：{reference_answer}
    AI的回答：{llm_answer}
    
    请判断 AI 的回答是否在事实层面与标准答案一致。
    忽略措辞差异。
    """
    comment = eval_llm.invoke(prompt)
    return {
        "score": comment.score,
        "comment": comment.comment,
    }


dataset_name = "General-Agent-Benchmark"
dataset_data = [
    # --- 第一类：常识与事实 (General Knowledge) ---
    {
        "input": "Python 语言是谁发明的？",
        "output": "Guido van Rossum"
    },
    {
        "input": "太阳系中体积最大的行星是哪一颗？",
        "output": "木星 (Jupiter)"
    },
    {
        "input": "泰坦尼克号是在哪一年沉没的？",
        "output": "1912年"
    },

    # --- 第二类：逻辑与数学 (Logic & Math) ---
    {
        "input": "我有3个苹果，吃掉1个，又买了5个，现在我有几个苹果？",
        "output": "7个"
    },
    {
        "input": "如果昨天是周二，那么后天是周几？",
        "output": "周五"
    },
    {
        "input": "25 的平方根是多少？",
        "output": "5"
    },

    # --- 第三类：多步推理 (Complex Reasoning) ---
    # 这类问题通常需要 Agent 进行搜索或深层思考
    {
        "input": "现任美国总统的出生地是哪个州？",
        "output": "取决于当前时间点 (例如拜登是宾夕法尼亚州，特朗普是纽约州)"
    },
    {
        "input": "《哈利波特》系列电影中扮演赫敏的演员，她也是哪部迪士尼真人电影的主角？",
        "output": "艾玛·沃特森 (Emma Watson)，她也是《美女与野兽》的主角。"
    },

    # --- 第四类：简单的指令遵循 (Instruction) ---
    {
        "input": "请把 'Hello World' 翻译成法语，只输出翻译结果，不要废话。",
        "output": "Bonjour le monde"
    },
    {
        "input": "写一个计算斐波那契数列的 Python 函数。",
        "output": "def fib(n): ..."
    }
]

client = Client()
if client.has_dataset(dataset_name=dataset_name):
    print(f"🔄 数据集 '{dataset_name}' 已存在，正在删除重建以确保数据最新...")
    client.delete_dataset(dataset_name=dataset_name)

print(f"📦 正在创建数据集: {dataset_name} ...")
dataset = client.create_dataset(
    dataset_name=dataset_name,
    description="包含常识、数学、逻辑和多步推理的通用 Agent 测试集"
)

inputs = [{"question": item["input"]} for item in dataset_data]
outputs = [{"answer": item["output"]} for item in dataset_data]

client.create_examples(
    inputs=inputs,
    outputs=outputs,
    dataset_id=dataset.id
)

if __name__ == '__main__':
    eval_res = evaluate(
        bridge_func,
        data=dataset_name,
        evaluators=[evaluator],
        experiment_prefix="agent-v1-test",
        max_concurrency=1
    )
