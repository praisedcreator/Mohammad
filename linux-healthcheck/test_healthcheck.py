import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

BASH=os.environ.get('PORTFOLIO_BASH') or (shutil.which('bash') if sys.platform=='linux' else None)
SCRIPT=Path(__file__).resolve().parent/'healthcheck.sh'


@unittest.skipUnless(BASH,'Bash fixture tests run on Linux, or with PORTFOLIO_BASH explicitly configured')
class HealthcheckTests(unittest.TestCase):
    def setUp(self):
        test_root=(SCRIPT.parent/'.runtime/tests').resolve()
        test_root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='portfolio-health-',dir=test_root)
        if not Path(self.temp.name).resolve().is_relative_to(test_root):raise RuntimeError('Test cleanup must remain inside the project')
        self.addCleanup(self.temp.cleanup)
        self.fixture=Path(self.temp.name)
        self.write_metrics()

    def write_metrics(self,total=1000,available=600,disk='25',load='1.0',cpus='4'):
        for name,text in {'meminfo':f'MemTotal: {total} kB\nMemAvailable: {available} kB\n',
                          'loadavg':f'{load} 0.1 0.1 1/2 42\n','disk_percent':disk+'\n','cpu_count':cpus+'\n'}.items():
            (self.fixture/name).write_text(text,encoding='utf-8',newline='\n')

    def run_check(self,*args):
        return subprocess.run([BASH,'--noprofile','--norc',SCRIPT.as_posix(),'--fixture-dir',self.fixture.as_posix(),*args],
                              capture_output=True,text=True,timeout=10)

    def test_healthy_summary(self):
        result=self.run_check();self.assertEqual(result.returncode,0,result.stderr)
        payload=json.loads(result.stdout)
        self.assertEqual(payload['memory_used_percent'],40)
        self.assertEqual(payload['load_per_cpu'],0.25)
        self.assertEqual(payload['mode'],'fixture')

    def test_memory_warning_boundary(self):
        self.write_metrics(available=150)
        result=self.run_check();self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'warning')

    def test_disk_warning_boundary(self):
        self.write_metrics(disk='85');self.assertEqual(self.run_check().returncode,1)

    def test_load_warning_is_scaled_by_cpu_count(self):
        self.write_metrics(load='6.0',cpus='4');self.assertEqual(self.run_check().returncode,1)

    def test_rounding_does_not_create_warning(self):
        self.write_metrics(total=100000,available=15001,disk='10',load='1')
        self.assertEqual(self.run_check().returncode,0)

    def test_missing_metric_fails_without_healthy_output(self):
        (self.fixture/'meminfo').write_text('MemTotal: 1000 kB\n')
        result=self.run_check();self.assertEqual(result.returncode,2)
        self.assertEqual(result.stdout,'')

    def test_out_of_range_metrics_rejected(self):
        for kwargs in [{'total':0},{'available':1001},{'cpus':'0'},{'disk':'101'},{'load':'-1'}]:
            with self.subTest(kwargs=kwargs):
                self.write_metrics(**kwargs);self.assertEqual(self.run_check().returncode,2)

    def test_shell_metacharacters_are_data(self):
        self.write_metrics(disk='1; echo injected')
        result=self.run_check();self.assertEqual(result.returncode,2)
        self.assertNotIn('injected',result.stdout)

    def test_missing_fixture_directory_rejected(self):
        result=self.run_check('--fixture-dir',str(self.fixture/'missing'))
        self.assertEqual(result.returncode,2)

    def test_unknown_argument_rejected(self):
        self.assertEqual(self.run_check('--unknown').returncode,2)

    def test_read_only_fixture_run(self):
        before={p.name:p.read_bytes() for p in self.fixture.iterdir()}
        self.run_check()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.fixture.iterdir()})

    def test_bash_syntax(self):
        result=subprocess.run([BASH,'-n',SCRIPT.as_posix()],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
