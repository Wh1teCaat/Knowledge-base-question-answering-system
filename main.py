from retriever import RAG

rag = RAG("./data", "./chroma_db")
retriever = rag.get_retriever()