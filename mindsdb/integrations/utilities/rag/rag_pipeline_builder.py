import pandas as pd
from langchain.storage import InMemoryByteStore

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.runnables import RunnableSerializable
from sqlalchemy import create_engine
from mindsdb.integrations.utilities.rag.pipelines.rag import LangChainRAGPipeline
from mindsdb.integrations.utilities.rag.settings import (
    DEFAULT_POOL_RECYCLE,
    RetrieverType,
    RAGPipelineModel
)
from mindsdb.integrations.utilities.rag.utils import documents_to_df


_retriever_strategies = {
    RetrieverType.SQL: lambda config: _create_pipeline_from_sql_retriever(config),
    RetrieverType.VECTOR_STORE: lambda config: _create_pipeline_from_vector_store(config),
    RetrieverType.AUTO: lambda config: _create_pipeline_from_auto_retriever(config),
    RetrieverType.MULTI: lambda config: _create_pipeline_from_multi_retriever(config),
}


def _create_pipeline_from_sql_retriever(config: RAGPipelineModel) -> LangChainRAGPipeline:
    documents_df = _process_documents_to_df(config)
    alchemyEngine = create_engine(
        config.db_connection_string, pool_recycle=DEFAULT_POOL_RECYCLE)
    db_connection = alchemyEngine.connect()

    documents_df.to_sql(config.table_name, db_connection, index=False, if_exists='replace')

    return LangChainRAGPipeline.from_sql_retriever(
        config=config
    )


def _create_pipeline_from_vector_store(config: RAGPipelineModel) -> LangChainRAGPipeline:

    return LangChainRAGPipeline.from_retriever(
        config=config
    )


def _create_pipeline_from_auto_retriever(config: RAGPipelineModel) -> LangChainRAGPipeline:
    return LangChainRAGPipeline.from_auto_retriever(
        config=config
    )


def _create_pipeline_from_multi_retriever(config: RAGPipelineModel) -> LangChainRAGPipeline:

    if config.text_splitter is None:
        config.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size, chunk_overlap=config.chunk_overlap
        )
    if config.parent_store is None:
        config.parent_store = InMemoryByteStore()

    return LangChainRAGPipeline.from_multi_vector_retriever(
        config=config
    )


def _process_documents_to_df(config: RAGPipelineModel) -> pd.DataFrame:
    return documents_to_df(config.content_column_name,
                           config.documents,
                           embeddings_model=config.embeddings_model,
                           with_embeddings=True)


def get_pipeline_from_retriever(config: RAGPipelineModel) -> RunnableSerializable:
    retriever_strategy = _retriever_strategies.get(config.retriever_type)
    if retriever_strategy:
        return retriever_strategy(config).with_returned_sources()
    else:
        raise ValueError(
            f'Invalid retriever type, must be one of: {list(_retriever_strategies.keys())}. Got {config.retriever_type}')


class RAG:
    def __init__(self, config: dict):
        config = RAGPipelineModel(**config)
        self.pipeline = get_pipeline_from_retriever(config)

    def __call__(self, question: str):
        return self.pipeline.invoke(question)
