from agent import RAGAgent

executor = RAGAgent().get_memory_runnable()
executor.invoke({"input": "生成一篇800字作文"},
                config={"configurable": {"session_id": "user_a"}})
executor.invoke({"input": "2025.11.8武汉天气"},
                config={"configurable": {"session_id": "user_b"}})
executor.invoke({"input": "刚刚我都问了什么"},
                config={"configurable": {"session_id": "user_a"}})
executor.invoke({"input": "刚刚我都问了什么"},
                config={"configurable": {"session_id": "user_b"}})
