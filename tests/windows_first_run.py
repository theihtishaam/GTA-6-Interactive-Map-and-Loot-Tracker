"""Optional Windows first-run test. Build the release ZIP first. Uses a public Python.org download."""
import json
import os
from pathlib import Path
from subprocess import Popen, run, STDOUT, CREATE_NO_WINDOW
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from urllib.request import ProxyHandler, build_opener
from zipfile import ZipFile
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
system = Path(os.environ['SystemRoot'])/'System32'
opener = build_opener(ProxyHandler({}))
env = {key: os.environ[key] for key in (
    "SystemRoot", "SystemDrive", "ComSpec", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
    "ProgramData", "ProgramFiles", "PROCESSOR_ARCHITECTURE", "PROCESSOR_ARCHITEW6432",
) if key in os.environ}
env["PATH"] = os.pathsep.join(map(str, [system, system/'WindowsPowerShell'/'v1.0']))
with TemporaryDirectory(prefix="GTA map player setup ") as folder:
    with ZipFile(root/'release'/'Leonida-Loot-Atlas-source.zip') as z:
        z.extractall(folder)
    project = Path(folder)/'Leonida-Loot-Atlas'
    runtime = project/'.atlas'
    runtime.mkdir()
    now = datetime.now(timezone.utc).isoformat()
    (runtime/'state.json').write_text(json.dumps({'lastRun':now,'interval':24,'sources':[],'reports':[],
        'bounty':{'interval':24,'lastRun':now,'sources':[],'reports':[]}}))
    log_file = project/'setup QA.log'
    def start():
        with log_file.open('wb') as log:
            return Popen('cmd.exe /d /c call "Start Atlas.cmd" -NoOpen -BundledOnly -Port 0', executable=str(system/'cmd.exe'),
                         cwd=project,env=env,stdout=log,stderr=STDOUT,creationflags=CREATE_NO_WINDOW)
    def stop():
        result = run('cmd.exe /d /c call "Stop Atlas.cmd"',executable=str(system/'cmd.exe'),cwd=project,
                     env=env,timeout=15,stdout=-1,stderr=STDOUT,creationflags=CREATE_NO_WINDOW)
        assert result.returncode==0,result.stdout.decode(errors='replace')
    def check_setup():
        proc=start()
        try:
            deadline=monotonic()+105
            while monotonic()<deadline:
                if proc.poll() is not None: raise RuntimeError(log_file.read_text(errors='replace'))
                try:
                    sess=json.loads((runtime/'launcher.json').read_text())
                    with opener.open(f"http://127.0.0.1:{sess['port']}/api/launcher",timeout=1) as r: api=json.load(r)
                    if api['instance']==sess['instance']: break
                except (ValueError,OSError): pass
                sleep(.2)
            else: raise RuntimeError(log_file.read_text(errors='replace'))
            assert api['version']=='0.1.1'
            with opener.open(f"http://127.0.0.1:{sess['port']}/",timeout=4) as r: assert b'GTA 6 Loot Map' in r.read()
            stop()
            assert proc.wait(timeout=10)==0
            return log_file.read_text(errors='replace')
        finally:
            if proc.poll() is None:
                try: stop()
                except Exception: pass
                proc.wait(timeout=10)
    first = check_setup()
    print(first,flush=True)
    assert 'Setting up Python 3.14.10' in first
    second = check_setup()
    assert 'Setting up Python 3.14.10' not in second
    stop()
    print('Verified official app-local Python download, successful run, cached second launch, Stop Atlas.cmd and repeated stop.')
