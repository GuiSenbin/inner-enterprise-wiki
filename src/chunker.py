"""
定位：知识编译切片层。
职责：优先使用 LangChain Markdown splitter，把 Markdown 文档编译成稳定文本切片。
依赖：可选依赖 langchain-text-splitters；缺失时回退到本地字符串滑窗。
"""


class MarkdownChunker:
    """优先按 Markdown 结构递归切分，依赖不可用时按固定窗口回退。"""

    def __init__(self, chunk_size=2000, overlap=300, use_langchain=True, splitter=None):
        """设置切片长度，并允许测试或调用方注入兼容 split_text 的 splitter。"""
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap 必须大于等于 0 且小于 chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.splitter = splitter if splitter is not None else self._create_langchain_splitter(use_langchain)

    def split(self, text):
        """返回非空切片；有 LangChain splitter 时优先使用其 Markdown 切分结果。"""
        if self.splitter is not None:
            chunks = [chunk for chunk in self.splitter.split_text(text) if chunk.strip()]
            if chunks:
                return chunks
        return self._fallback_split(text)

    def _create_langchain_splitter(self, use_langchain):
        """创建 LangChain Markdown splitter；未安装依赖时返回 None 走本地回退。"""
        if not use_langchain:
            return None
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
            from langchain_text_splitters.base import Language
        except ImportError:
            return None

        return RecursiveCharacterTextSplitter.from_language(
            language=Language.MARKDOWN,
            chunk_size=self.chunk_size,
            chunk_overlap=self.overlap,
        )

    def _fallback_split(self, text):
        """短文档单块，长文档按固定窗口切分并保留上下文重叠。"""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        step = self.chunk_size - self.overlap
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += step
        return chunks
