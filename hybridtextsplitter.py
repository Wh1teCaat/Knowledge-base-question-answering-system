from langchain_community.document_transformers import EmbeddingsRedundantFilter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import Literal
import dotenv
import os
from cachembedding import CacheEmbedding

dotenv.load_dotenv()


class HybridTextSplitter:
    def __init__(
        self,
        chunk_size=500,
        chunk_overlap=50,
        embedding_model=CacheEmbedding(),
        buffer_size=4,
        threshold_type: Literal["percentile", "standard_deviation", "interquartile", "gradient"] = "percentile",
        threshold_amount=95.0,
        similarity_threshold=0.97,
        enable_filter=True,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model
        self.buffer_size = buffer_size
        self.threshold_type = threshold_type
        self.threshold_amount = threshold_amount
        self.similarity_threshold = similarity_threshold
        self.enable_filter = enable_filter

        # 粗切分
        self.rough_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size*2,
            chunk_overlap=self.chunk_overlap*2,
            separators=["\n\n", "\n", "。", "！", "？"]
        )
        # 控制长度
        self.lens_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name=os.getenv("MODEL_NAME"),
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", "。", "！", "？", "，"],
        )
        # 按语义切
        self.semantic_splitter = SemanticChunker(
            embeddings=self.embedding_model,
            buffer_size=self.buffer_size,
            breakpoint_threshold_type=self.threshold_type,
            breakpoint_threshold_amount=self.threshold_amount,
        )
        # 冗余过滤
        if self.enable_filter:
            self.filter = EmbeddingsRedundantFilter(
                embeddings=self.embedding_model,
                similarity_threshold=self.similarity_threshold,
            )

    def split(self, documents: list[Document]) -> list[Document]:
        """完整切分流程"""
        print("Step 1️⃣ 粗切分 ...")
        results = self.rough_splitter.split_documents(documents)
        print(f"  → 粗切分结果: {len(results)} 段")

        print("Step 2️⃣ 长度控制切分 ...")
        results = self.lens_splitter.split_documents(results)
        print(f"  → 长度控制后: {len(results)} 段")

        if self.enable_filter:
            print("Step 3️⃣ 冗余过滤 (EmbeddingsRedundantFilter) ...")
            results = self.filter.transform_documents(results)
            print(f"  → 去重后: {len(results)} 段")

        print("Step 4️⃣ 语义切分 (SemanticChunker) ...")
        results = self.semantic_splitter.split_documents(results)
        print(f"  → 语义切分结果: {len(results)} 段")

        print("✅ 切分完成")
        return results
