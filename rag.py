import os
import sys
sys.path.append('.')

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from config import RAG_DOCUMENTS_PATH, VECTOR_STORE_PATH, API_BASE, EMBEDDING_MODEL, OPENAI_API_KEY

print("[RAG] 开始初始化RAG系统...")

def load_documents():
    """加载指定目录下的所有文本文件"""
    if not os.path.exists(RAG_DOCUMENTS_PATH):
        os.makedirs(RAG_DOCUMENTS_PATH, exist_ok=True)
        print(f"[RAG] 创建文档目录: {RAG_DOCUMENTS_PATH}")
        return []
    
    documents = []
    for file in os.listdir(RAG_DOCUMENTS_PATH):
        if file.endswith('.txt'):
            file_path = os.path.join(RAG_DOCUMENTS_PATH, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                doc = Document(page_content=content, metadata={"source": file})
                documents.append(doc)
                print(f"[RAG] 成功加载文件: {file}")
            except Exception as e:
                print(f"[RAG] 加载文件 {file} 时出错: {e}")
    
    print(f"[RAG] 共加载 {len(documents)} 个文档")
    return documents

def split_documents(documents):
    """分块文档以便于向量化"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=150,
        chunk_overlap=20,
        length_function=len,
        separators=["\n\n", "\n", "。", "！", "？", "；", "，", " "]
    )
    
    if not documents:
        print("[RAG] 警告：没有文档可分割")
        return []
    
    splits = text_splitter.split_documents(documents)
    print(f"[RAG] 文档分割完成，共生成 {len(splits)} 个文档块")
    
    # 预览，确认分割有效
    for i, chunk in enumerate(splits[:3]):
        preview = chunk.page_content.replace('\n', ' ')[:60]
        print(f"[RAG] 块 {i+1} 预览: {preview}...")
    
    return splits

def get_rag_processor():
    """
    获取RAG处理器单例
    返回一个包含search方法的简单对象，与response_engine兼容
    """
    print("[RAG] 开始创建RAG处理器...")
    
    # 加载文档
    documents = load_documents()
    if not documents:
        print("[RAG] 错误：没有加载到任何文档")
        return None
    
    # 分割文档
    splits = split_documents(documents)
    if not splits:
        print("[RAG] 错误：文档分割后为空")
        return None
    
    try:
        # 初始化嵌入模型
        print(f"[RAG] 初始化嵌入模型，使用: {EMBEDDING_MODEL}")
        embeddings = OpenAIEmbeddings(
            openai_api_base=API_BASE,
            openai_api_key=OPENAI_API_KEY,
            model=EMBEDDING_MODEL
        )
        
        # 创建向量存储
        print(f"[RAG] 创建向量存储到: {VECTOR_STORE_PATH}")
        
        # 删除旧的向量存储
        import shutil
        if os.path.exists(VECTOR_STORE_PATH):
            shutil.rmtree(VECTOR_STORE_PATH, ignore_errors=True)
        
        # 创建新的向量存储
        vector_store = Chroma.from_documents(
            documents=splits,
            embedding=embeddings,
            persist_directory=VECTOR_STORE_PATH
        )
        
        
        # 创建检索器
        retriever = vector_store.as_retriever(
            search_kwargs={"k": 3}
        )
        
        print("[RAG] RAG处理器创建成功！")
        
        # 返回一个简单的处理器对象
        class SimpleRAGProcessor:
            def __init__(self, retriever):
                self.retriever = retriever
            
            def search(self, query):
                try:
                    print(f"[RAG] 正在搜索: {query}")

                    docs = self.retriever.invoke(query)
                    
                    if not docs:
                        return "未找到相关产品信息。"
                    
                    results = []
                    for i, doc in enumerate(docs, 1):
                        source = doc.metadata.get("source", "未知")
                        content = doc.page_content[:200].replace('\n', ' ')
                        results.append(f"[来源: {source}] {content}...")
                    
                    return "\n".join(results)
                except Exception as e:
                    print(f"[RAG] 搜索出错: {e}")
                    return f"检索过程出错: {str(e)}"
        
        return SimpleRAGProcessor(retriever)
        
    except Exception as e:
        print(f"[RAG] 创建RAG处理器失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def search_documents(query):
    processor = get_rag_processor()
    if processor:
        return processor.search(query)
    return "RAG检索功能暂不可用"


def test_retriever():
    """测试检索器的方法"""
    processor = get_rag_processor()
    if processor and processor.retriever:
        retriever = processor.retriever
        print(f"[测试] 检索器类型: {type(retriever)}")
        print(f"[测试] 检索器可用方法: {[m for m in dir(retriever) if not m.startswith('_')]}")
        
        # 尝试调用
        try:
            result = retriever.invoke("测试")
            print(f"[测试] invoke() 成功: {len(result)} 个结果")
        except Exception as e:
            print(f"[测试] invoke() 失败: {e}")
            
        try:
            result = retriever.get_relevant_documents("测试")
            print(f"[测试] get_relevant_documents() 成功: {len(result)} 个结果")
        except Exception as e:
            print(f"[测试] get_relevant_documents() 失败: {e}")

if __name__ == "__main__":
    test_retriever()