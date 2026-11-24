from __future__ import annotations
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from optical.linux_service import DiscService, OpticalError, dependency_message, safe_volume_label, split_dnd_paths
from optical.models import OperationResult

class FakeProcess:
    def __init__(self, lines=("25% done\n", "100% done\n"), code=0):
        self.stdout=io.StringIO("".join(lines));self.code=code;self.terminated=False
    def wait(self):return self.code
    def poll(self):return self.code
    def terminate(self):self.terminated=True

class FakeRunner:
    def __init__(self,code=0):self.argv=[];self.code=code
    def popen(self,argv):self.argv=argv;return FakeProcess(code=self.code)

class PureLogicTests(unittest.TestCase):
    def test_label_is_portable_and_bounded(self):
        self.assertEqual(safe_volume_label(" 观海 test/盘 "),"TEST")
        self.assertEqual(safe_volume_label(""),"GUANHAI_DISC")
        self.assertLessEqual(len(safe_volume_label("x"*100)),32)
    def test_dnd_parser_uses_tcl(self):
        paths=split_dnd_paths("{/tmp/a b} /tmp/c",lambda s:["/tmp/a b","/tmp/c"])
        self.assertEqual([p.name for p in paths],["a b","c"])
    def test_embedded_meipass_tool_is_preferred(self):
        with tempfile.TemporaryDirectory() as d:
            tool=Path(d)/"tools"/"amd64"/"xorriso"
            tool.parent.mkdir(parents=True);tool.write_text("#!/bin/sh\n");tool.chmod(0o755)
            with patch.object(sys,"_MEIPASS",d,create=True):
                self.assertEqual(DiscService(FakeRunner()).xorriso,str(tool))
    def test_dependency_hint_is_actionable(self):
        msg=dependency_message({"xorriso":None})
        self.assertIn("安装镜像",msg);self.assertIn("tools/<架构>",msg)
    def test_no_windows_dependency(self):
        source=(Path(__file__).resolve().parents[1]/"optical"/"linux_service.py").read_text(encoding="utf-8")
        self.assertNotIn("win32",source);self.assertNotIn("comtypes",source)

class CommandTests(unittest.TestCase):
    def setUp(self):
        self.runner=FakeRunner();self.service=DiscService(self.runner,xorriso="/mock/xorriso")
    def test_cd_burn_uses_mastered_joliet_and_close(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"资料.txt";src.write_text("ok",encoding="utf-8")
            result=self.service.burn("/dev/sr0",[src],"test")
        self.assertTrue(result.ok);a=self.runner.argv
        self.assertIn("-joliet",a);self.assertIn("-rockridge",a);self.assertEqual(a[a.index("-close")+1],"on")
        self.assertIn("/资料.txt",a);self.assertNotIn("-udf",a)
    def test_udf_burn_and_format(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/"a";src.write_text("x")
            self.service.burn("/dev/sr1",[src],"v",burn_mode="UDF")
            self.assertIn("-udf",self.runner.argv)
            self.service.format("/dev/sr1","v")
        self.assertIn("-format",self.runner.argv);self.assertIn("as_needed",self.runner.argv)
    def test_blank_modes(self):
        self.service.erase("/dev/sr0");self.assertIn("fast",self.runner.argv)
        self.service.erase("/dev/sr0",True);self.assertIn("all",self.runner.argv)
    def test_rejects_non_optical_target_without_process(self):
        with self.assertRaises(OpticalError):self.service.erase("/dev/sda")
        self.assertEqual(self.runner.argv,[])
    def test_error_contains_process_output(self):
        self.runner.code=2
        with self.assertRaisesRegex(OpticalError,"xorriso 返回错误"):
            self.service.erase("/dev/sr0")
    def test_missing_tool_has_readable_error(self):
        service=DiscService(FakeRunner(),xorriso=None)
        with patch("shutil.which",return_value=None),patch("pathlib.Path.glob",return_value=[]):
            with self.assertRaisesRegex(OpticalError,"未找到 xorriso"):service.erase("/dev/sr0")
    def test_progress_is_parsed(self):
        values=[];self.service.erase("/dev/sr0",callback=lambda _t,v:values.append(v))
        self.assertEqual(values,[None,25,99,100])

class ExportTests(unittest.TestCase):
    def test_export_files_without_hardware(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/"src";dst=root/"dst";src.mkdir();(src/"a.txt").write_text("hello")
            progress=[];r=DiscService(FakeRunner(),xorriso="x").export_files([src],str(dst),lambda _t,v:progress.append(v))
            self.assertTrue(r.ok);self.assertEqual((dst/"src"/"a.txt").read_text(),"hello");self.assertEqual(progress[-1],99)

if __name__=="__main__":unittest.main()
