from run_agent import AIAgent
from hermes_cli import providers
from hermes_cli import runtime_provider as rp


def test_bedrock_provider_is_builtin_with_bedrock_invoke_mode():
    pdef = providers.get_provider("bedrock")

    assert pdef is not None
    assert pdef.id == "bedrock"
    assert pdef.transport == "bedrock_invoke"
    assert pdef.auth_type == "aws"
    assert providers.determine_api_mode("bedrock") == "bedrock_invoke"


def test_runtime_provider_resolves_bedrock_from_aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("AWS_REGION", "ap-southeast-3")
    monkeypatch.setattr(rp, "resolve_provider", lambda *a, **k: "bedrock")
    monkeypatch.setattr(
        rp,
        "_get_model_config",
        lambda: {"provider": "bedrock", "default": "deepseek.v3.2"},
    )

    resolved = rp.resolve_runtime_provider(requested="bedrock")

    assert resolved["provider"] == "bedrock"
    assert resolved["api_mode"] == "bedrock_invoke"
    assert resolved["model"] == "deepseek.v3.2"
    assert resolved["region"] == "ap-southeast-3"
    assert resolved["api_key"] == "aws-env"
    assert resolved["base_url"] == "bedrock://ap-southeast-3"


def test_bedrock_build_invoke_body_uses_deepseek_message_shape():
    agent = object.__new__(AIAgent)
    agent.model = "deepseek.v3.2"
    agent.max_tokens = 512
    agent.request_overrides = {}
    agent.reasoning_config = None

    body = agent._bedrock_build_invoke_body(
        {
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ]
        }
    )

    assert body == {
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ],
        "max_tokens": 512,
    }


def test_bedrock_response_to_chat_completion_parses_deepseek_content():
    agent = object.__new__(AIAgent)
    agent.model = "deepseek.v3.2"

    response = agent._bedrock_response_to_chat_completion(
        {"choices": [{"message": {"content": "Halo!"}, "finish_reason": "stop"}]}
    )

    assert response.model == "deepseek.v3.2"
    assert response.choices[0].finish_reason == "stop"
    assert response.choices[0].message.content == "Halo!"
    assert response.choices[0].message.tool_calls is None


def test_bedrock_build_invoke_body_uses_claude_shape():
    agent = object.__new__(AIAgent)
    agent.model = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    agent.max_tokens = 1024

    body = agent._bedrock_build_invoke_body(
        {
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Hello"},
            ],
            "temperature": 0.2,
        }
    )

    assert body == {
        "anthropic_version": "bedrock-2023-05-31",
        "system": "Be concise.",
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Hello"}]},
        ],
        "max_tokens": 1024,
        "temperature": 0.2,
    }


def test_bedrock_build_invoke_body_uses_nova_shape():
    agent = object.__new__(AIAgent)
    agent.model = "amazon.nova-pro-v1:0"
    agent.max_tokens = 2048

    body = agent._bedrock_build_invoke_body(
        {
            "messages": [{"role": "user", "content": "Summarize"}],
            "temperature": 0.3,
            "top_p": 0.9,
        }
    )

    assert body == {
        "messages": [{"role": "user", "content": [{"text": "Summarize"}]}],
        "inferenceConfig": {
            "maxTokens": 2048,
            "temperature": 0.3,
            "topP": 0.9,
        },
    }


def test_bedrock_extract_text_parses_claude_and_nova_payloads():
    agent = object.__new__(AIAgent)

    assert agent._bedrock_extract_text(
        {"content": [{"type": "text", "text": "Claude says hi"}]}
    ) == "Claude says hi"
    assert agent._bedrock_extract_text(
        {"output": {"message": {"content": [{"text": "Nova says hi"}]}}}
    ) == "Nova says hi"


def test_bedrock_extract_stream_delta_parses_common_event_shapes():
    agent = object.__new__(AIAgent)

    assert agent._bedrock_extract_stream_delta(
        {"choices": [{"delta": {"content": "Deep"}}]}
    ) == "Deep"
    assert agent._bedrock_extract_stream_delta(
        {"type": "content_block_delta", "delta": {"text": "Claude"}}
    ) == "Claude"
    assert agent._bedrock_extract_stream_delta({"outputText": "Nova"}) == "Nova"


def test_bedrock_streaming_invoke_fires_deltas_and_returns_combined_text():
    class _FakeClient:
        def invoke_model_with_response_stream(self, **kwargs):
            self.kwargs = kwargs
            return {
                "body": [
                    {"chunk": {"bytes": b'{"choices":[{"delta":{"content":"Hel"}}]}'}},
                    {"chunk": {"bytes": b'{"choices":[{"delta":{"content":"lo"}}]}'}},
                ]
            }

    agent = object.__new__(AIAgent)
    agent.model = "deepseek.v3.2"
    agent.base_url = "bedrock://ap-southeast-3"
    agent.max_tokens = 128
    agent._bedrock_region = "ap-southeast-3"
    agent._bedrock_client = _FakeClient()
    agent._stream_callback = None
    seen = []
    agent.stream_delta_callback = seen.append

    response = agent._bedrock_invoke_model_stream_create(
        {"model": "deepseek.v3.2", "messages": [{"role": "user", "content": "Hi"}]}
    )

    assert seen == ["Hel", "lo"]
    assert response.choices[0].message.content == "Hello"
    assert agent._bedrock_client.kwargs["modelId"] == "deepseek.v3.2"


def test_bedrock_converse_tool_config_maps_openai_tools():
    agent = object.__new__(AIAgent)

    tool_config = agent._bedrock_converse_tool_config([
        {
            "type": "function",
            "function": {
                "name": "search_files",
                "description": "Search files",
                "parameters": {
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"],
                },
            },
        }
    ])

    assert tool_config == {
        "tools": [
            {
                "toolSpec": {
                    "name": "search_files",
                    "description": "Search files",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {"pattern": {"type": "string"}},
                            "required": ["pattern"],
                        }
                    },
                }
            }
        ]
    }


def test_bedrock_converse_request_maps_messages_tool_uses_and_results():
    agent = object.__new__(AIAgent)
    agent.max_tokens = 256

    request = agent._bedrock_build_converse_request(
        {
            "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "messages": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Find config"},
                {
                    "role": "assistant",
                    "content": "Searching",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "search_files",
                                "arguments": '{"pattern":"config"}',
                            },
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "found"},
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_files",
                        "description": "Search files",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            "temperature": 0.1,
        }
    )

    assert request["modelId"] == "anthropic.claude-3-5-sonnet-20240620-v1:0"
    assert request["system"] == [{"text": "Be concise."}]
    assert request["inferenceConfig"] == {"maxTokens": 256, "temperature": 0.1}
    assert request["messages"] == [
        {"role": "user", "content": [{"text": "Find config"}]},
        {
            "role": "assistant",
            "content": [
                {"text": "Searching"},
                {
                    "toolUse": {
                        "toolUseId": "call_1",
                        "name": "search_files",
                        "input": {"pattern": "config"},
                    }
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": "call_1",
                        "content": [{"text": "found"}],
                    }
                }
            ],
        },
    ]
    assert request["toolConfig"]["tools"][0]["toolSpec"]["name"] == "search_files"


def test_bedrock_converse_response_normalizes_tool_use_to_openai_tool_calls():
    agent = object.__new__(AIAgent)
    agent.model = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    response = agent._bedrock_response_to_chat_completion(
        {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "I'll search."},
                        {
                            "toolUse": {
                                "toolUseId": "tooluse_1",
                                "name": "search_files",
                                "input": {"pattern": "bedrock"},
                            }
                        },
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
        }
    )

    msg = response.choices[0].message
    assert response.choices[0].finish_reason == "tool_calls"
    assert msg.content == "I'll search."
    assert msg.tool_calls[0].id == "tooluse_1"
    assert msg.tool_calls[0].function.name == "search_files"
    assert msg.tool_calls[0].function.arguments == '{"pattern":"bedrock"}'
    assert response.usage.prompt_tokens == 10
    assert response.usage.completion_tokens == 5
    assert response.usage.total_tokens == 15


def test_bedrock_converse_create_uses_converse_when_tools_present():
    class _FakeClient:
        def converse(self, **kwargs):
            self.kwargs = kwargs
            return {
                "output": {"message": {"role": "assistant", "content": [{"text": "done"}]}},
                "stopReason": "end_turn",
            }

    agent = object.__new__(AIAgent)
    agent.model = "amazon.nova-pro-v1:0"
    agent.max_tokens = 128
    agent._bedrock_client = _FakeClient()

    response = agent._bedrock_converse_create(
        {
            "model": "amazon.nova-pro-v1:0",
            "messages": [{"role": "user", "content": "Hi"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "todo",
                        "description": "Manage todos",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        }
    )

    assert response.choices[0].message.content == "done"
    assert agent._bedrock_client.kwargs["toolConfig"]["tools"][0]["toolSpec"]["name"] == "todo"


def test_bedrock_converse_stream_accumulates_text_and_tool_use():
    class _FakeClient:
        def converse_stream(self, **kwargs):
            self.kwargs = kwargs
            return {
                "stream": [
                    {"contentBlockDelta": {"delta": {"text": "Let me "}}},
                    {
                        "contentBlockStart": {
                            "start": {
                                "toolUse": {
                                    "toolUseId": "tooluse_1",
                                    "name": "search_files",
                                }
                            }
                        }
                    },
                    {"contentBlockDelta": {"delta": {"toolUse": {"input": '{"pattern"'}}}},
                    {"contentBlockDelta": {"delta": {"toolUse": {"input": ':"bedrock"}'}}}},
                    {"messageStop": {"stopReason": "tool_use"}},
                ]
            }

    agent = object.__new__(AIAgent)
    agent.model = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    agent.max_tokens = 128
    agent._bedrock_client = _FakeClient()
    seen = []
    agent.stream_delta_callback = seen.append
    agent._stream_callback = None
    agent._stream_delivered_text = ""
    agent._stream_last_delta = ""
    agent._stream_last_delta_time = 0
    agent._stream_needs_break = False

    response = agent._bedrock_converse_stream_create(
        {
            "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "messages": [{"role": "user", "content": "Find bedrock"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_files",
                        "description": "Search files",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
        }
    )

    assert seen == ["Let me "]
    msg = response.choices[0].message
    assert msg.content == "Let me "
    assert response.choices[0].finish_reason == "tool_calls"
    assert msg.tool_calls[0].id == "tooluse_1"
    assert msg.tool_calls[0].function.name == "search_files"
    assert msg.tool_calls[0].function.arguments == '{"pattern":"bedrock"}'

