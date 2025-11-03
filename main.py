from agent import RAGAgent

executor = RAGAgent().get_executor()
executor.invoke({"input": "医学上现实增强技术的应用"})
executor.invoke({"input": "2025.11.2武汉天气"})
executor.invoke({"input": "刚刚我都问了什么"})