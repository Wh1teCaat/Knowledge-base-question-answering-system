import os

import dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

dotenv.load_dotenv()

llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL")
)

result = llm.invoke("你好，请用一句话介绍你自己。")
print(result.content)