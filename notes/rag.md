# RAG (retrieval-augmented generation)

- Chunk size: start with about 500 tokens per chunk and a 50-token overlap; test 300 to 800.
- Retrieve the top 4 chunks first, then re-rank if answers miss facts.
- Measure retrieval with recall@k before blaming the LLM.
- Always show the source chunk next to the answer.
