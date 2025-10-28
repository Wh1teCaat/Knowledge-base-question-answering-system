from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from typing import Literal


class HybridTextSplitter:
    def __init__(
        self,
        chunk_size=500,
        chunk_overlap=50,
        embedding_model=None,
        threshold_type: Literal["percentile", "standard_deviation", "interquartile", "gradient"] = "percentile",
        threshold_amount=90.0,
        enable_filter=True,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model or OpenAIEmbeddings(model="text-embedding-3-large")
        self.threshold_type = threshold_type
        self.threshold_amount = threshold_amount
        self.enable_filter = enable_filter

        self.rough_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "，"]
        )

        self.semantic_splitter = SemanticChunker(
            embeddings=self.embedding_model,
            breakpoint_threshold_type=self.threshold_type,
            breakpoint_threshold_amount=self.threshold_amount,
        )
