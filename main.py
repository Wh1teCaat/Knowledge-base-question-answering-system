from agent import RAGAgent

executor = RAGAgent().get_executor()
executor.invoke({"input": "什么是现实增强技术"})
executor.invoke({"input": "2025.11.2武汉天气"})