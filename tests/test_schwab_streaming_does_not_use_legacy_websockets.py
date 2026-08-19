def test_schwab_streaming_does_not_use_legacy_websockets():
    import inspect
    import schwab.streaming

    source = inspect.getsource(schwab.streaming)

    assert "websockets.legacy" not in source