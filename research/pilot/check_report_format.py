"""Dependency-free checks of the fixed request schema's supported JSON subset.

Runtime also checks the upstream response model; this publication check does
not claim to rerun GraphRAG or assess any report's factual content.
"""
import json
import math

from probe_runtime import REPORT_SCHEMA


def validate_report(text):
    def unique(pairs):
        value={}
        for key,item in pairs:
            assert key not in value,'Duplicate report field'
            value[key]=item
        return value
    value=json.loads(text,object_pairs_hook=unique)

    def validate(item,schema):
        assert set(schema)<={'type','properties','required','additionalProperties','items'}
        kind=schema['type']
        if kind=='object':
            assert isinstance(item,dict)
            assert set(schema['required'])<=set(item)
            assert schema['additionalProperties'] is False
            assert set(item)<=set(schema['properties'])
            for name,child in item.items():validate(child,schema['properties'][name])
        elif kind=='array':
            assert isinstance(item,list)
            for child in item:validate(child,schema['items'])
        elif kind=='string':assert isinstance(item,str)
        elif kind=='number':assert type(item) in {int,float} and math.isfinite(item)
        else:raise AssertionError('Unsupported schema feature; do not silently skip it')
    validate(value,REPORT_SCHEMA)
    return value
