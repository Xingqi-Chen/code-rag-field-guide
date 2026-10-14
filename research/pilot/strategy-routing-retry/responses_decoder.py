"""Offline Responses decoder for the separately recorded DRIFT retry.

No I/O, credentials, networking, retries or semantic/JSON repair. Based on the
frozen decoder, with ordered visible-text aggregation matching OpenAI Python
2.54.0 Response.output_text. Callers retain usage/model/output-limit checks and
strict PrimerResponse validation. Diagnostics contain allowlisted labels and
counts only; never response text, arbitrary errors, identifiers or reasoning.
"""
import json


class DecodeError(Exception):
    """Fixed public reason code plus a text-free diagnostic snapshot."""
    def __init__(self, code, diagnostics):
        super().__init__(code)
        self.diagnostics = dict(diagnostics)


def decode_generation(raw, content_type, *, diagnostics=None):
    """Decode completed JSON/SSE, concatenating all visible text in wire order.

    `diagnostics` can be an empty dict owned by the worker; it is populated on
    success or failure. Never select only one message, strip fences, extract a
    JSON-looking substring, use deltas as a final answer, or expose reasoning.
    Unknown/refusal/tool output remains a failure for this no-tools experiment.
    """
    d = diagnostics if diagnostics is not None else {}
    d.update(decoder_version=1, event_count=0, done_item_count=0,
             assistant_message_count=0, visible_text_block_count=0,
             reasoning_item_count=0, output_item_count=0, provider_usage=None)

    def fail(code):
        d['error_category'] = code
        raise DecodeError(code, d)

    def obj(text):
        try:
            value = json.loads(text)
        except (ValueError, TypeError):
            fail('responses_invalid_json')
        if not isinstance(value, dict):
            fail('responses_invalid_object')
        return value

    items, terminal, response_id = {}, None, None
    sse = 'text/event-stream' in (content_type or '').lower() or raw.lstrip().startswith(('data:', 'event:'))
    d['transport'] = 'sse' if sse else 'json'
    if sse:
        for frame in raw.replace('\r\n', '\n').split('\n\n'):
            data = '\n'.join(line[5:].removeprefix(' ') for line in frame.splitlines() if line.startswith('data:'))
            if not data or data == '[DONE]':
                continue
            event = obj(data)
            d['event_count'] += 1
            if terminal is not None:
                fail('responses_after_terminal')
            kind = event.get('type')
            if not isinstance(kind, str):
                fail('responses_invalid_event_type')
            if kind == 'error':
                fail('responses_stream_error')
            if 'response' in event:
                response = event['response']
                if (not isinstance(response, dict) or not isinstance(response.get('id'), str)
                        or not response['id'] or response_id not in (None, response['id'])):
                    fail('responses_identity_mismatch')
                response_id = response['id']
            if kind == 'response.output_item.done':
                index, item = event.get('output_index'), event.get('item')
                if (type(index) is not int or index < 0 or index in items
                        or not isinstance(item, dict) or not isinstance(item.get('id'), str)
                        or not item['id'] or any(x['id'] == item['id'] for x in items.values())):
                    fail('responses_invalid_item')
                items[index] = item
                d['done_item_count'] = len(items)
            elif kind in {'response.completed', 'response.incomplete', 'response.failed'}:
                terminal = event.get('response')
                if not isinstance(terminal, dict) or kind != 'response.' + str(terminal.get('status')):
                    fail('responses_invalid_terminal')
        if terminal is None:
            fail('responses_stream_unfinished')
    else:
        terminal = obj(raw)
    status = terminal.get('status')
    d['terminal_status'] = status if isinstance(status, str) and status in {'completed', 'incomplete', 'failed', 'cancelled', 'in_progress', 'queued'} else 'other'
    usage = terminal.get('usage')
    # Preserve numerically valid usage even if visible-message decoding fails.
    if isinstance(usage, dict):
        keys = ('input_tokens', 'output_tokens', 'total_tokens')
        if all(type(usage.get(k)) is int and usage[k] >= 0 for k in keys) and usage['input_tokens'] + usage['output_tokens'] == usage['total_tokens']:
            d['provider_usage'] = {k: usage[k] for k in keys}
    if terminal.get('error') is not None or status != 'completed':
        fail('responses_not_completed')
    output = terminal.get('output')
    if not isinstance(output, list):
        fail('responses_missing_output')
    recovered = not output and bool(items)
    d['recovered_output_items'] = recovered
    if recovered:
        if sorted(items) != list(range(len(items))):
            fail('responses_item_gap')
        # Sorted contiguous indexes establish the provider's output order.
        output = [items[i] for i in range(len(items))]
    elif any(i >= len(output) or output[i] != item for i, item in items.items()):
        fail('responses_item_conflict')
    d['output_item_count'] = len(output)
    texts, ids = [], set()
    for item in output:
        if not isinstance(item, dict):
            fail('responses_invalid_item')
        item_id = item.get('id')
        if isinstance(item_id, str):
            if item_id in ids:
                fail('responses_duplicate_output_id')
            ids.add(item_id)
        if item.get('type') == 'reasoning':
            d['reasoning_item_count'] += 1
            continue
        if item.get('type') != 'message' or item.get('role') != 'assistant' or item.get('status') not in (None, 'completed'):
            fail('responses_unexpected_output')
        d['assistant_message_count'] += 1
        content = item.get('content')
        if not isinstance(content, list) or not content:
            fail('responses_nontext_output')
        for block in content:
            if not isinstance(block, dict) or block.get('type') != 'output_text' or not isinstance(block.get('text'), str):
                fail('responses_nontext_output')
            d['visible_text_block_count'] += 1
            texts.append(block['text'])
    visible = ''.join(texts)
    d['visible_character_count'] = len(visible)
    if not visible.strip():
        # Empty/reasoning-only responses remain failures, never invented answers.
        fail('responses_empty_visible_output')
    if not isinstance(usage, dict):
        fail('responses_missing_usage')
    return {'model': terminal.get('model'),
            'choices': [{'finish_reason': 'stop', 'message': {'content': visible}}],
            'usage': {'prompt_tokens': usage.get('input_tokens'), 'completion_tokens': usage.get('output_tokens'),
                      'total_tokens': usage.get('total_tokens')},
            'responses_transport': 'sse' if sse else 'json', 'recovered_output_items': recovered}
