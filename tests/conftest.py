import pytest


@pytest.fixture(autouse=True)
def stateful_tabs_in_apptest(monkeypatch):
    """Streamlit 1.55's AppTest omits the new tab widget from its protobuf.

    Supply the same string_value sent by the real browser on reruns. This only
    patches the test driver, not the app or its session-state implementation.
    """
    from streamlit.testing.v1.element_tree import ElementTree
    original = ElementTree.get_widget_states
    def states(tree):
        result = original(tree)
        if tree._runner is not None:
            for node in tree:
                proto = getattr(node,'proto',None)
                if proto is not None and hasattr(proto,'tab_container') and proto.HasField('tab_container'):
                    identity = proto.tab_container.id
                    if identity and 'active_tab' in tree._runner.session_state:
                        result.widgets.add(id=identity,string_value=tree._runner.session_state['active_tab'])
        return result
    monkeypatch.setattr(ElementTree,'get_widget_states',states)
