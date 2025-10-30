import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_community.document_transformers import EmbeddingsRedundantFilter
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from functools import lru_cache
from typing import Literal
import dotenv
import hashlib
import os

dotenv.load_dotenv()


class HybridTextSplitter:
    def __init__(
        self,
        chunk_size=500,
        chunk_overlap=50,
        embedding_model=None,
        buffer_size=4,
        threshold_type: Literal["percentile", "standard_deviation", "interquartile", "gradient"] = "percentile",
        threshold_amount=95.0,
        similarity_threshold=0.97,
        enable_filter=True,
        cache_path="./cache/embeddings_cache.json",
        batch_size=16,
        thread_num=4
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_model = embedding_model or OllamaEmbeddings(
            model=os.getenv("LOCAL_EMBEDDING"),
            base_url=os.getenv("LOCAL_BASE_URL"),
        )
        self.buffer_size = buffer_size
        self.threshold_type = threshold_type
        self.threshold_amount = threshold_amount
        self.similarity_threshold = similarity_threshold
        self.enable_filter = enable_filter
        self.cache_path = cache_path
        self.batch_size = batch_size
        self.thread_num = thread_num

        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        self.cache = self._load_cache()

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

        self.semantic_splitter.embeddings.embed_query = self._cache_embed_query
        self.semantic_splitter.embeddings.embed_documents = self._parallel_embed
        self.filter.embeddings.embed_documents = self._parallel_embed

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if not data:
                    return {}
                return json.loads(data)
        return {}

    def _save_cache(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f)

    @staticmethod
    def _text_hash(text: str) -> str:
        """对文本生成唯一哈希"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @lru_cache(maxsize=None)
    def _cache_embed_query(self, text: str) -> list[float]:
        """单句嵌入"""
        _hash = self._text_hash(text)
        if _hash in self.cache:
            return self.cache[_hash]
        vec = self.embedding_model.embed_query(text)
        self.cache[_hash] = vec
        self._save_cache()
        return vec

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入"""
        results, to_compute = [], []
        for text in texts:
            _hash = self._text_hash(text)
            if _hash in self.cache:
                results.append(self.cache[_hash])
            else:
                to_compute.append(text)

        if to_compute is not None:
            vectors = self.embedding_model.embed_documents(to_compute)
            for t, v in zip(to_compute, vectors):
                _hash = self._text_hash(t)
                self.cache[_hash] = v
                results.append(v)
            self._save_cache()
        return results

    def _parallel_embed(self, texts: list[str]) -> list[list[float]]:
        """多线程并行批量嵌入"""
        results = []
        batches = [texts[idx:idx+self.batch_size] for idx in range(0, len(texts), self.batch_size)]
        with ThreadPoolExecutor(max_workers=self.thread_num) as executor:
            # 列表元素是每个线程的控制句柄
            futures = [executor.submit(self._embed_batch, batch) for batch in batches]
            for future in as_completed(futures):    # 按完成顺序取结果
                results.extend(future.result())
        return results

    def split(self, documents: list[Document]) -> list[Document]:
        results = self.rough_splitter.split_documents(documents)
        print(len(results))
        results = self.lens_splitter.split_documents(results)
        print(len(results))
        if self.enable_filter:
            results = self.filter.transform_documents(results)
            print(len(results))
        results = self.semantic_splitter.split_documents(results)
        print(len(results))
        return results
