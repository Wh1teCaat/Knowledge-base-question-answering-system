from retriever import RAG

rag = RAG("./data", "./chroma_db")
retriever = rag.get_retriever()
# from multiloader import MultiLoader
# from hybridtextsplitter import HybridTextSplitter
#
# loader = MultiLoader("./data")
# docs = loader.load()
# print("文件加载完成")
#
# splitter = HybridTextSplitter()
# docs = splitter.split(docs)
# print("文档切分完成")
