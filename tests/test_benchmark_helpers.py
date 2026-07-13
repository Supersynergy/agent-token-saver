from scripts.bench_news_agent_stack import est_tokens as news_tokens
from scripts.graph_query_benchmark import est_tokens as graph_tokens


def test_token_proxies_match_bytes_over_four():
    assert news_tokens("12345678") == 2
    assert graph_tokens(b"12345678") == 2
