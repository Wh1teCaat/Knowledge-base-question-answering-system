from langchain_core.document_loaders.base import BaseLoader
from langchain_community.document_loaders import (
    TextLoader,
    PyPDFLoader,
    CSVLoader,
    JSONLoader,
    UnstructuredHTMLLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document
from datasets import load_dataset
import os


class MultiLoader(BaseLoader):
    """加载指定目录下的 huggingface 数据集和本地文件"""
    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def _convert_huggingface_path(self, dirname: str) -> str:
        """将 huggingface 缓存目录转换为 huggingface path"""
        return dirname.replace("___", "/").replace("---", "/")

    def _is_huggingface_path(self, filename) -> bool:
        return "___" in filename or "---" in filename or "/" in filename

    def _load_file(self, filename: str):
        """加载 huggingface 数据或本地文件"""
        # 加载 huggingface 数据
        if self._is_huggingface_path(filename):
            print(f"😀加载 HuggingFace 数据集：{filename}")
            try:
                dataset = load_dataset(
                    filename,
                    split="train",
                    cache_dir="./data/huggingface",
                )
            except Exception as e:
                raise RuntimeError(f"❌ 加载数据集失败: {e}")
            # 加载成 document
            docs = [
                Document(
                    page_content=record.get("positive_doc")[0].get("content"),
                    metadata={"question": record.get("question"),
                              "answer": record.get("answer"),
                              "datatype": record.get("positive_doc")[0].get("datatype"),
                              "title": record.get("positive_doc")[0].get("title")}
                ) for record in dataset
            ]
            return docs

        # 加载本地文件
        path = os.path.join(self.path, filename)
        ext = os.path.splitext(path)[1].lower()
        if ext == '.txt':
            loader = TextLoader(path, encoding="utf-8")
        elif ext == '.pdf':
            loader = PyPDFLoader(path)
        elif ext == '.csv':
            loader = CSVLoader(path)
        elif ext == '.json':
            loader = JSONLoader(
                file_path=path,
                jq_schema="""
                .[] | {
                    question : .question,
                    answer : .answer,
                    content : .context
                }
                """,
                metadata_func=lambda record, metadata: {
                    "question": record.get("question"),
                    "answer": record.get("answer"),
                    "source": metadata.get("source"),
                },
                content_key="content"
            )
        elif ext == '.html':
            loader = UnstructuredHTMLLoader(path, mode="elements", strategy="fast")
        elif ext == '.md':
            loader = UnstructuredMarkdownLoader(path, strategy="fast")
        else:
            return [Document(page_content="", metadata={"source": path, "error": "unsupported file type"})]
        try:
            return loader.load()
        except Exception as e:
            return [Document(page_content="", metadata={"source": path, "error": str(e)})]

    def load(self):
        """加载路径下所有文件"""
        # 读取目录下所有文件名
        items = os.listdir(self.path)
        docs = []
        for item in items:
            if item == "huggingface":
                # 获取 huggingface 文件夹下所有缓存目录
                dirs = os.listdir(os.path.join(self.path, item))
                for dirname in dirs:
                    path = self._convert_huggingface_path(dirname)
                    docs.extend(self._load_file(path))
            else:
                docs.extend(self._load_file(item))
        return docs
