import os

from langchain_community.vectorstores import Chroma
from multiloader import MultiLoader
from hybridtextsplitter import HybridTextSplitter
from cachembedding import CacheEmbedding


class RAG:
    def __init__(self, data_path, db_path, cache_path):
        self.data_path = data_path
        self.db_path = db_path
        self.cache_path = cache_path

    def build_vector_db(self):
        loader = MultiLoader(self.data_path)
        docs = loader.load()
        print("文件加载完成")

        splitter = HybridTextSplitter(self.cache_path)
        docs = splitter.split(docs)
        print("文档切分完成")

        embedding_model = splitter.embedding_model
        db = Chroma.from_documents(
            documents=docs,
            embedding=embedding_model,
            persist_directory=self.db_path
        )
        print("✅ 向量数据库构建完成")
        return db

    def get_retriever(self):
        if not os.path.exists(self.db_path) or not os.listdir(self.db_path):
            print("⚠️ 未检测到持久化文件，正在重新构建数据库...")
            db = self.build_vector_db()
        else:
            print("✅ 加载已有数据库...")
            db = Chroma(
                persist_directory=self.db_path,
                embedding_function=CacheEmbedding(self.cache_path)
            )
        retriever = db.as_retriever()
        return retriever
