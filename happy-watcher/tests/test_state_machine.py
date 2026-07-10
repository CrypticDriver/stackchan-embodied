from happy_watcher.state_machine import SessionSnapshot, SessionState, Watcher


def snap(sid, state, title="修bug", detail=""):
    return SessionSnapshot(sid, title, state, detail)


def test_first_observation_emits():
    w = Watcher()
    events = w.observe([snap("s1", SessionState.WAITING_INPUT)])
    assert len(events) == 1
    assert events[0].kind == "attention"
    assert "审批" in events[0].speak


def test_same_state_dedup():
    w = Watcher()
    w.observe([snap("s1", SessionState.WAITING_INPUT)])
    assert w.observe([snap("s1", SessionState.WAITING_INPUT)]) == []


def test_state_change_emits_again():
    w = Watcher()
    w.observe([snap("s1", SessionState.RUNNING)])
    events = w.observe([snap("s1", SessionState.COMPLETED)])
    assert events[0].kind == "happy"
    assert "干完" in events[0].speak


def test_failed_includes_detail():
    w = Watcher()
    events = w.observe([snap("s1", SessionState.FAILED, detail="测试挂了")])
    assert events[0].kind == "pouty"
    assert "测试挂了" in events[0].speak


def test_quiet_hours_no_speech():
    w = Watcher(quiet=True)
    events = w.observe([snap("s1", SessionState.WAITING_INPUT)])
    assert len(events) == 1
    assert events[0].speak is None
    assert events[0].kind == "attention"


def test_running_is_silent_thinking():
    w = Watcher()
    events = w.observe([snap("s1", SessionState.RUNNING)])
    assert events[0].kind == "thinking"
    assert events[0].speak is None


def test_batch_merge():
    w = Watcher()
    events = w.observe([snap(f"s{i}", SessionState.WAITING_INPUT, title=f"项目{i}") for i in range(4)])
    speaking = [e for e in events if e.speak]
    assert len(speaking) == 1
    assert "4个活儿" in speaking[0].speak


def test_long_title_truncated():
    w = Watcher()
    events = w.observe([snap("s1", SessionState.COMPLETED, title="一个特别特别特别长的任务标题超过限制")])
    assert len(events[0].speak) < 30
