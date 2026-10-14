"""Synthetic offline fixtures: never historical failed responses or API calls."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from responses_decoder import DecodeError, decode_generation
ROOT = Path(__file__).resolve().parents[3]


def frozen_old_decoder():
    # Extract only the function, avoiding imports, credentials and worker code.
    source = ROOT / 'research/pilot/probe_runtime.py'
    node = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'decode_generation')
    ns = {'json': json, 'Stop': RuntimeError}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), ns)
    return ns['decode_generation']


def message(text, identifier='msg_1'):
    return {'id': identifier, 'type': 'message', 'role': 'assistant', 'status': 'completed',
            'content': [{'type': 'output_text', 'text': text}]}


def response(output, **extra):
    return {'id': 'resp_1', 'status': 'completed', 'model': 'gpt-5.6-luna', 'output': output,
            'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}, **extra}


def frame(event):return 'data: ' + json.dumps(event) + '\n\n'

def stream(output, *, terminal_output=None):
    return ''.join(frame({'type': 'response.output_item.done', 'output_index': i, 'item': item}) for i, item in enumerate(output)) + frame({'type': 'response.completed', 'response': response(output if terminal_output is None else terminal_output)})


def content(value):return value['choices'][0]['message']['content']


class DecoderTests(unittest.TestCase):
    def decode(self, obj):return decode_generation(json.dumps(obj), 'application/json')
    def reject(self, raw, category, content_type='text/event-stream'):
        with self.assertRaises(DecodeError) as cm:decode_generation(raw, content_type)
        self.assertEqual(str(cm.exception), category)
        return cm.exception.diagnostics

    def test_single_message_old_and_new_identical(self):
        raw=json.dumps(response([message('hello')]))
        self.assertEqual(decode_generation(raw,'application/json'), frozen_old_decoder()(raw,'application/json'))

    def test_two_messages_old_rejects_new_aggregates(self):
        raw=json.dumps(response([message('first','m1'),message('second','m2')]))
        with self.assertRaisesRegex(RuntimeError,'responses_empty_or_multiple_messages'):frozen_old_decoder()(raw,'application/json')
        self.assertEqual(content(decode_generation(raw,'application/json')),'firstsecond')

    def test_two_message_sse_aggregation(self):
        self.assertEqual(content(decode_generation(stream([message('first','m1'),message('second','m2')]),'text/event-stream')),'firstsecond')

    def test_multiple_content_blocks(self):
        m=message('a');m['content'].append({'type':'output_text','text':'b'})
        self.assertEqual(content(self.decode(response([m]))),'ab')

    def test_split_json_reassembles_without_repair(self):
        text=content(self.decode(response([message('{"intermediate_answer":"a",','m1'),message('"score":1,"follow_up_queries":["q"]}','m2')])))
        self.assertEqual(json.loads(text)['score'],1)

    def test_commentary_plus_json_not_cherry_picked(self):
        text=content(self.decode(response([message('Here is JSON: ','m1'),message('{"score":1}','m2')])))
        with self.assertRaises(json.JSONDecodeError):json.loads(text)
        self.assertTrue(text.startswith('Here is JSON: '))

    def test_two_complete_json_documents_not_cherry_picked(self):
        text=content(self.decode(response([message('{"score":1}','m1'),message('{"score":2}','m2')])))
        with self.assertRaises(json.JSONDecodeError):json.loads(text)

    def test_empty_and_reasoning_only_are_failures(self):
        for output in [[],[{'type':'reasoning','id':'r1','summary':[{'text':'PRIVATE_CANARY'}]}],[message('  ')]]:
            d=self.reject(json.dumps(response(output)),'responses_empty_visible_output','application/json')
            self.assertNotIn('PRIVATE_CANARY',json.dumps(d))
            self.assertEqual(d['provider_usage']['total_tokens'],15)

    def test_reasoning_excluded(self):
        v=self.decode(response([{'type':'reasoning','id':'r1','summary':[{'text':'PRIVATE_CANARY'}]},message('visible')]))
        self.assertEqual(content(v),'visible');self.assertNotIn('PRIVATE_CANARY',json.dumps(v))

    def test_refusal_and_tool_rejected(self):
        m=message('');m['content']=[{'type':'refusal','refusal':'PRIVATE_CANARY'}]
        self.reject(json.dumps(response([m])),'responses_nontext_output','application/json')
        self.reject(json.dumps(response([{'id':'tool1','type':'function_call','arguments':'PRIVATE_CANARY'}])),'responses_unexpected_output','application/json')

    def test_incomplete_and_failed_rejected(self):
        for status in ['incomplete','failed']:
            self.reject(json.dumps(response([message('partial')],status=status)),'responses_not_completed','application/json')

    def test_delta_without_terminal_not_success(self):
        self.reject(frame({'type':'response.output_text.delta','delta':'partial'}),'responses_stream_unfinished')

    def test_done_without_terminal_not_success(self):
        self.reject(frame({'type':'response.output_item.done','output_index':0,'item':message('partial')}),'responses_stream_unfinished')

    def test_done_recovery_preserved(self):
        v=decode_generation(stream([message('one')],terminal_output=[]),'text/event-stream')
        self.assertEqual(content(v),'one');self.assertTrue(v['recovered_output_items'])

    def test_duplicate_done_rejected(self):
        f=frame({'type':'response.output_item.done','output_index':0,'item':message('a')})
        self.reject(f+f,'responses_invalid_item')

    def test_duplicate_done_id_rejected(self):
        self.reject(stream([message('a'),message('b')]),'responses_invalid_item')

    def test_duplicate_terminal_output_id_rejected(self):
        self.reject(json.dumps(response([message('a'),message('b')])),'responses_duplicate_output_id','application/json')

    def test_done_terminal_conflict_rejected(self):
        self.reject(stream([message('a')],terminal_output=[message('b')]),'responses_item_conflict')

    def test_noncontiguous_done_recovery_rejected(self):
        raw=frame({'type':'response.output_item.done','output_index':1,'item':message('a')})+frame({'type':'response.completed','response':response([])})
        self.reject(raw,'responses_item_gap')

    def test_wrong_identity_rejected(self):
        raw=frame({'type':'response.created','response':{'id':'r0'}})+frame({'type':'response.completed','response':response([message('a')])})
        self.reject(raw,'responses_identity_mismatch')

    def test_output_after_terminal_rejected(self):
        self.reject(stream([message('a')])+frame({'type':'response.output_text.delta','delta':'late'}),'responses_after_terminal')

    def test_done_marker_after_terminal_allowed(self):
        self.assertEqual(content(decode_generation(stream([message('a')])+'data: [DONE]\n\n','text/event-stream')),'a')

    def test_top_level_output_text_not_fallback(self):
        self.reject(json.dumps(response([],output_text='NOT_VALIDATED')),'responses_empty_visible_output','application/json')

    def test_invalid_and_missing_usage_not_fabricated(self):
        self.reject(json.dumps(response([message('a')],usage=None)),'responses_missing_usage','application/json')
        d={};v=decode_generation(json.dumps(response([message('a')],usage={'input_tokens':True,'output_tokens':5,'total_tokens':6})),'application/json',diagnostics=d)
        self.assertIsNone(d['provider_usage']);self.assertIs(v['usage']['prompt_tokens'],True)
        # Numeric validity remains the caller's existing validate_usage job.

    def test_diagnostics_never_reflect_arbitrary_labels(self):
        d=self.reject(json.dumps(response([{'type':'PRIVATE_CANARY'}],status='SECRET_STATUS')),'responses_not_completed','application/json')
        self.assertNotIn('SECRET_STATUS',json.dumps(d));self.assertNotIn('PRIVATE_CANARY',json.dumps(d))

    def test_malformed_event_type_and_status_remain_fixed_errors(self):
        self.reject(frame({'type':{'PRIVATE_CANARY':'value'}}),'responses_invalid_event_type')
        d=self.reject(json.dumps(response([],status={'PRIVATE_CANARY':'value'})),'responses_not_completed','application/json')
        self.assertEqual(d['terminal_status'],'other');self.assertNotIn('PRIVATE_CANARY',json.dumps(d))

    def test_strict_primer_contract_from_pinned_source(self):
        try:
            from pydantic import BaseModel, Field, ValidationError
        except ImportError:
            self.skipTest('Run .cache/graphrag-venv/bin/python for pinned Pydantic check')
        pinned=ROOT/'.cache/ms-graphrag/graphrag-5faaaf4f5685fa2056fa8c3bf9342cb089f2942f/packages/graphrag/graphrag/query/structured_search/drift_search/primer.py'
        tree=ast.parse(pinned.read_text());node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='PrimerResponse')
        ns={'BaseModel':BaseModel,'Field':Field};exec(compile(ast.Module(body=[node],type_ignores=[]),str(pinned),'exec'),ns)
        primer=ns['PrimerResponse'];good={'intermediate_answer':'brief','score':1,'follow_up_queries':['q']}
        self.assertEqual(primer.model_validate(good,strict=True).model_dump(),good)
        # 2000 characters and >=5 are descriptive prompt instructions, not validators.
        self.assertNotIn('minLength',primer.model_json_schema()['properties']['intermediate_answer'])
        for bad in [dict(good,score='1'),dict(good,score=1.5),dict(good,follow_up_queries='q')]:
            with self.assertRaises(ValidationError):primer.model_validate(bad,strict=True)
        old=ROOT/'research/pilot/strategy-routing/runtime/bounded.py'
        node=next(n for n in ast.parse(old.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='strict_json')
        ns={'json':json,'Halt':RuntimeError};exec(compile(ast.Module(body=[node],type_ignores=[]),str(old),'exec'),ns)
        for bad_json in ['{"score":1,"score":2}','{"score":NaN}','commentary {"score":1}','{"score":1}{"score":2}']:
            with self.assertRaises(RuntimeError):ns['strict_json'](bad_json)
        count=0
        for path in sorted((ROOT/'research/pilot/strategy-routing/results/wire').glob('event-*.json')):
            event=json.loads(path.read_text())
            if event['event']['stage']!='primer' or event['event']['status']!='validated':continue
            text=event['response_envelope']['response']['choices'][0]['message']['content']
            # Validate archived normalized visible text, not a fabricated raw replay.
            primer.model_validate(ns['strict_json'](text),strict=True);count+=1
        self.assertEqual(count,7)

    def test_installed_sdk_output_text_property_equivalence(self):
        sdk=ROOT/'.cache/graphrag-venv/lib/python3.12/site-packages/openai/types/responses/response.py'
        if not sdk.exists():self.skipTest('Optional pinned local SDK source not installed')
        tree=ast.parse(sdk.read_text());cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Response')
        node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='output_text');node=deepcopy(node);node.decorator_list=[]
        ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(sdk),'exec'),ns)
        proxy=NS(output=[NS(type='message',content=[NS(type='output_text',text='a')]),NS(type='message',content=[NS(type='output_text',text='b')])])
        self.assertEqual(ns['output_text'](proxy),content(self.decode(response([message('a','m1'),message('b','m2')]))))


if __name__=='__main__':unittest.main(verbosity=2)
