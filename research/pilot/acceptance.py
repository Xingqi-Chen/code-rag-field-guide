"""Original held-out acceptance checks. NEVER include in a retrieval index.

No feature solution is supplied. Each feature starts from the same pre-change
snapshot. These tests intentionally fail there and are not part of fast CI.
"""
from collections import UserDict
import pytest
import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict


class TestF01:
    def test_union_preserves_type_case_precedence_and_inputs(self):
        left = CaseInsensitiveDict({'Accept': 'old', 'X-One': '1'})
        right = UserDict({'ACCEPT': 'new', 'X-Two': '2'})
        result = left | right
        assert type(result) is CaseInsensitiveDict
        assert result['accept'] == 'new'
        assert list(result) == ['ACCEPT', 'X-One', 'X-Two']
        assert dict(left) == {'Accept': 'old', 'X-One': '1'}
        assert dict(right) == {'ACCEPT': 'new', 'X-Two': '2'}

    def test_reverse_plain_dict_union(self):
        right = CaseInsensitiveDict({'ACCEPT': 'right'})
        left = {'Accept': 'left', 'Other': 'ok'}
        result = left | right
        assert type(result) is CaseInsensitiveDict
        assert dict(result) == {'ACCEPT': 'right', 'Other': 'ok'}
        assert list(result) == ['ACCEPT', 'Other']
        assert left == {'Accept': 'left', 'Other': 'ok'}
        assert dict(right) == {'ACCEPT': 'right'}

    def test_inplace_keeps_identity(self):
        value = CaseInsensitiveDict({'Accept': 'old'})
        alias = value
        value |= UserDict({'ACCEPT': 'new', 'X-New': '2'})
        assert value is alias
        assert dict(value) == {'ACCEPT': 'new', 'X-New': '2'}
        assert list(value) == ['ACCEPT', 'X-New']

    @pytest.mark.parametrize('operator', ['left', 'right', 'inplace'])
    def test_non_mapping_rejected(self, operator):
        value = CaseInsensitiveDict({'A': '1'})
        with pytest.raises(TypeError):
            if operator == 'left':
                value | [('B', '2')]
            elif operator == 'right':
                [('B', '2')] | value
            else:
                value |= [('B', '2')]

    def test_merged_headers_still_prepare_normally(self):
        headers = CaseInsensitiveDict({'Accept': 'old'}) | {'ACCEPT': 'new'}
        prepared = requests.Request('GET', 'https://example.invalid/', headers=headers).prepare()
        assert prepared.headers['accept'] == 'new'


class RecordingAdapter(BaseAdapter):
    def __init__(self, redirect=False):
        self.seen = []
        self.redirect = redirect

    def send(self, request, **kwargs):
        self.seen.append(kwargs.get('timeout'))
        response = requests.Response()
        response.request = request
        response.url = request.url
        response._content = b''
        response.status_code = 302 if self.redirect and len(self.seen) == 1 else 200
        if response.status_code == 302:
            response.headers['Location'] = '/next'
        return response

    def close(self):
        pass


def configured(default=None, redirect=False):
    session = requests.Session()
    session.trust_env = False
    # Proposed public attribute, no constructor-signature change required.
    session.default_timeout = default
    adapter = RecordingAdapter(redirect)
    session.mount('https://', adapter)
    return session, adapter


class TestF02:
    def test_attribute_exists_and_preserves_old_default(self):
        session = requests.Session()
        assert session.default_timeout is None

    @pytest.mark.parametrize('value', [3.0, (1.0, 4.0)])
    @pytest.mark.parametrize('entry', ['get', 'post', 'request'])
    def test_omitted_timeout_uses_session_value(self, value, entry):
        session, adapter = configured(value)
        if entry == 'request':
            session.request('GET', 'https://example.invalid/')
        else:
            getattr(session, entry)('https://example.invalid/')
        assert adapter.seen == [value]

    @pytest.mark.parametrize('value', [None, 7.0, (2.0, 9.0)])
    def test_explicit_timeout_wins_including_none(self, value):
        session, adapter = configured(3.0)
        session.get('https://example.invalid/', timeout=value)
        assert adapter.seen == [value]

    def test_redirect_keeps_effective_timeout(self):
        session, adapter = configured((1.0, 4.0), redirect=True)
        session.get('https://example.invalid/')
        assert adapter.seen == [(1.0, 4.0), (1.0, 4.0)]

    def test_direct_send_contract_unchanged(self):
        session, adapter = configured(3.0)
        prepared = requests.Request('GET', 'https://example.invalid/').prepare()
        session.send(prepared)
        assert adapter.seen == [None]

    def test_different_sessions_do_not_share_defaults(self):
        first, first_adapter = configured(3.0)
        second, second_adapter = configured(5.0)
        first.get('https://example.invalid/')
        second.get('https://example.invalid/')
        assert first_adapter.seen == [3.0]
        assert second_adapter.seen == [5.0]

    def test_mutating_default_between_requests(self):
        session, adapter = configured(3.0)
        session.get('https://example.invalid/')
        session.default_timeout = (2.0, 6.0)
        session.get('https://example.invalid/')
        assert adapter.seen == [3.0, (2.0, 6.0)]
