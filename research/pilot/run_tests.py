"""Bounded offline test runner; makes no model calls and disables socket I/O."""
import argparse
import os
from pathlib import Path
import sys
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'.cache/pilot/source'


def forbidden(*args, **kwargs):
    raise RuntimeError('Network sockets disabled for this pilot test run')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', choices=['regression','F01','F02'])
    parser.add_argument('--candidate', help='Reviewed candidate directory under .cache/pilot/candidates')
    args=parser.parse_args()
    source=SOURCE
    if args.candidate:
        source=Path(args.candidate).resolve()
        assert source.is_relative_to((ROOT/'.cache/pilot/candidates').resolve()), 'candidate outside isolated area'
        assert source.is_dir()
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    # The project's conftest is reviewed; no httpbin fixture is selected.
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(source/'src'))
    import requests
    assert Path(requests.__file__).resolve()==source/'src/requests/__init__.py'
    assert requests.__version__=='2.32.3'
    import pytest
    paths = ['tests/test_structures.py','tests/test_hooks.py','tests/test_adapters.py',
             'tests/test_requests.py::TestCaseInsensitiveDict',
             'tests/test_utils.py::TestGuessJSONUTF',
             'tests/test_requests.py::TestRequests::test_should_strip_auth_host_change',
             'tests/test_requests.py::TestRequests::test_should_strip_auth_http_downgrade',
             'tests/test_requests.py::TestRequests::test_rewind_body_failed_seek']
    paths = [str(SOURCE/p) for p in paths] if args.suite=='regression' else [str(HERE/'acceptance.py')+'::Test'+args.suite]
    print('Requests 2.32.3; '+('reviewed candidate' if args.candidate else 'fixed source snapshot')+'; TCP/DNS disabled; suite='+args.suite,flush=True)
    # Prevent personal netrc/proxy inspection during request preparation.
    with patch('socket.socket.connect',forbidden), patch('socket.socket.connect_ex',forbidden), \
         patch('socket.create_connection',forbidden), patch('socket.getaddrinfo',forbidden), \
         patch('requests.sessions.get_netrc_auth',return_value=None), \
         patch('requests.sessions.get_environ_proxies',return_value={}), \
         patch('requests.utils.get_environ_proxies',return_value={}):
        result=pytest.main(['-q','--tb=short','-o','addopts=', '-p','no:cacheprovider',
                            '--basetemp',str(ROOT/'.cache/pilot/pytest-tmp'),*paths])
    raise SystemExit(result)

if __name__=='__main__':main()
