"""Real Data -> Transport.dispatch -> supervisor, only the child is synthetic."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

def check_supervisor(data_factory):
    import probe_runtime as probe
    import transport
    from bounded import read
    previous=probe.supervise
    data=data_factory()
    assert probe.supervise is previous and previous.__module__=='probe_runtime'
    actual_popen=subprocess.Popen;calls=[]
    with tempfile.TemporaryDirectory() as tmp:
        request=Path(tmp)/'request-01.json';response=Path(tmp)/'response-01.json'
        request.write_text('{}')
        def popen(argv,**kwargs):
            assert argv==[sys.executable,str(Path(transport.__file__).resolve()),'worker',str(request),str(response)]
            calls.append(argv[2])
            # Starts an actual harmless process through the actual supervisor.
            # It cannot import the live worker, read credentials or send HTTP.
            code=('import json,sys;from pathlib import Path; p=Path(sys.argv[1]);'
                  'p.write_text(json.dumps({"http_status":200,"response":{"synthetic":True}}));'
                  'p.with_suffix(".dispatch.json").write_text(json.dumps({"dispatch_started":True}))')
            return actual_popen([sys.executable,'-c',code,str(response)],**kwargs)
        with patch.object(transport,'check_authorization',lambda:None),patch.object(probe.subprocess,'Popen',popen):
            result=transport.Transport().dispatch(request,response,5)
        assert result=={'http_status':200,'response':{'synthetic':True},'request_dispatched':True}
        assert calls==['worker']
    return data,{'real_data_initialized':True,'supervisor_unchanged':True,'real_controller_dispatch':True,
                 'real_supervisor':True,'synthetic_child_processes':1,'live_workers':0,'real_api_calls':0}
