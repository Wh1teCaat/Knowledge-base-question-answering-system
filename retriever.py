from langchain_community.vectorstores import Chroma

from multiloader import MultiLoader
from hybridtextsplitter import HybridTextSplitter


class RAG:
    def __init__(self, data_path, db_path):
        self.data_path = data_path
        self.db_path = db_path

    def build_vector_db(self):
        loader = MultiLoader(self.data_path)
        docs = loader.load()

        splitter = HybridTextSplitter()
        docs = splitter.split(docs)

        embedding_model = splitter.embedding_model
        db = Chroma.from_documents(
            documents=docs,
            embedding=embedding_model,
            persist_directory=self.db_path
        )
        db.persist()
        return db

    def get_retriever(self):
        try:
            db = Chroma(persist_directory=self.db_path)
        except Exception as e:
            print(e)
            db = self.build_vector_db()
        retriever = db.as_retriever()
        return retriever
