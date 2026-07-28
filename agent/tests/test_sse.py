from yuanqi_agent.sse import encode_sse


def test_encode_sse_returns_one_complete_frame() -> None:
    payload = encode_sse(
        "uiData",
        {"uiData": {"type": "approval_card", "riskLevel": "high"}},
    )

    assert payload.count(b"\n\n") == 1
    assert payload.startswith(b"event: uiData\n")
    assert b'"type":"approval_card"' in payload
    assert payload.endswith(b"\n\n")
