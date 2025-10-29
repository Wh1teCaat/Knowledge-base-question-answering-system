from multiloader import MultiLoader
from hybridtextsplitter import HybridTextSplitter

loader = MultiLoader("./data")
docs = loader.load()
print(len(docs))

splitter = HybridTextSplitter()
docs = splitter.split(docs)
