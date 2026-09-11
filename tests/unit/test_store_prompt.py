from datamind_gateway.prompts import EXTERNAL_DATA_POLICY, STORE_AGENT_EMBEDDING_POLICY, build_store_request


def test_store_prompt_separates_embedding_from_llm():
    prompt = build_store_request("写入这份文档")
    assert "DATAMIND__EMBEDDING__*" in prompt
    assert "DATAMIND__LLM__API_BASE" in prompt
    assert "zcloud" in prompt
    assert "不得绕过向量索引伪造成功" in prompt
    assert prompt.endswith("写入这份文档")


def test_embedding_policy_is_shared_constant():
    assert STORE_AGENT_EMBEDDING_POLICY == build_store_request("").split(
        "\n\n用户入库请求", 1
    )[0]


def test_external_store_prompt_forbids_memory_and_skills():
    prompt = build_store_request("外部文档", external=True)
    assert EXTERNAL_DATA_POLICY in prompt
    assert "禁止写入或删除 Memory、Skills" in prompt
