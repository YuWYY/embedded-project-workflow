"""Contract/failure tests; synthetic outputs are never native-build evidence.
Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
Run: python -B -m unittest discover -s tests -p test_cubemx_rtos.py
Also run with python -B -O to ensure no safety gate depends on assert.
"""
from pathlib import Path
import hashlib
import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("adapter", ROOT / "skills/embedded-project-workflow/scripts/cubemx_rtos.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
ORIGINAL = (ROOT / "examples/cubemx-rtos/rtos_ownership.ioc").read_bytes()


def generated(words=256, capacity=8, dynamic=False):
    text = '/* USER CODE BEGIN Includes */\n#include "app.h"\n/* USER CODE END Includes */\n'
    for name, depth in (("Producer", words), ("Consumer", 256)):
        allocation = dynamic and name == "Producer"
        if not allocation:
            text += f"uint32_t {name}Stack[{depth}];\nosStaticThreadDef_t {name}TCB;\n"
        text += f'const osThreadAttr_t {name}_attributes = {{.name="{name}",'
        if allocation:
            text += f".stack_size={depth}*4,"
        else:
            text += f".stack_mem=&{name}Stack[0],.stack_size=sizeof({name}Stack),.cb_mem=&{name}TCB,.cb_size=sizeof({name}TCB),"
        text += ".priority=(osPriority_t)osPriorityNormal};\n"
        text += f"{name}Handle = osThreadNew({name}_Entry, NULL, &{name}_attributes);\n"
    text += f"uint8_t SamplesStorage[{capacity} * sizeof(uint32_t)];\n"
    text += 'const osMessageQueueAttr_t Samples_attributes={.name="Samples",.cb_mem=&SamplesTCB,.cb_size=sizeof(SamplesTCB),.mq_mem=&SamplesStorage,.mq_size=sizeof(SamplesStorage)};\n'
    text += f"SamplesHandle = osMessageQueueNew({capacity}, sizeof(uint32_t), &Samples_attributes);\n"
    text += "__weak void Producer_Entry(void *argument) { /* deliberately present fallback */ }\n"
    return text


def fake_map(words=256, capacity=8, dynamic=False):
    text = "    Producer_Entry 0x08000101 Thumb Code 42 user_app.o(i.Producer_Entry)\n"
    text += "    Consumer_Entry 0x08000181 Thumb Code 42 user_app.o(i.Consumer_Entry)\n"
    if not dynamic:
        text += f"    ProducerStack 0x20000000 Data {words * 4} app_freertos.o(.bss)\n"
    return text + f"    ConsumerStack 0x20004000 Data 1024 app_freertos.o(.bss)\n    SamplesStorage 0x20005000 Data {capacity * 4} app_freertos.o(.bss)\n"


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cubemx-adapter-unit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        for folder in ("Core/Src", "Core/Inc", "APP", "MDK-ARM/out"):
            (self.project / folder).mkdir(parents=True, exist_ok=True)
        self.ioc = self.project / "rtos_ownership.ioc"
        self.ioc.write_bytes(ORIGINAL)
        (self.project / ".mxproject").write_text("[PreviousLibFiles]\nLibFiles=Core\\Inc\\FreeRTOSConfig.h;\n", encoding="utf-8")
        self.source = self.project / "APP/user_app.c"
        self.source.write_text("void Producer_Entry(void *argument) {}\nvoid Consumer_Entry(void *argument) {}\n", encoding="utf-8")
        (self.source.parent / "app.h").write_text("void Producer_Entry(void *argument);\n", encoding="utf-8")
        self.generated = self.project / "Core/Src/app_freertos.c"
        self.generated.write_text(generated(), encoding="utf-8")
        (self.project / "Core/Src/main.c").write_text("int main(void) {}\n", encoding="utf-8")
        (self.project / "Core/Inc/FreeRTOSConfig.h").write_text("#define configSUPPORT_STATIC_ALLOCATION 1\n#define configSUPPORT_DYNAMIC_ALLOCATION 1\n", encoding="utf-8")
        self.xml = self.project / "MDK-ARM/rtos_ownership.uvprojx"
        self.xml.write_text(r'''<Project><Targets><Target><TargetName>Unit</TargetName><pCCUsed>5060960::V5.06 update 7 (build 960)::.\ARMCC</pCCUsed><uAC6>0</uAC6>
<TargetOption><TargetCommonOption><Device>STM32G474RETx</Device><PackID>Keil.STM32G4xx_DFP.2.0.0</PackID><OutputDirectory>out</OutputDirectory><ListingPath>out</ListingPath><OutputName>unit</OutputName><AfterMake><RunUserProg1>1</RunUserProg1><UserProg1Name /></AfterMake></TargetCommonOption><Cads><VariousControls><IncludePath>../APP;../Core/Inc</IncludePath></VariousControls></Cads></TargetOption>
<Groups><Group><GroupName>App</GroupName><Files><File><FileName>user_app.c</FileName><FileType>1</FileType><FilePath>../APP/user_app.c</FilePath></File><File><FileName>app_freertos.c</FileName><FileType>1</FileType><FilePath>../Core/Src/app_freertos.c</FilePath></File></Files></Group></Groups></Target></Targets></Project>''', encoding="utf-8")
        self.map = self.project / "MDK-ARM/out/unit.map"
        self.map.write_text(fake_map(), encoding="utf-8")
        self.tools = {key: str(self.root / key) for key in ("cubemx", "firmware", "uv4", "armcc", "pack")}
        self.installation = {"paths": self.tools, "profile": a.PROFILE}

    def plan(self, dynamic=False):
        if dynamic:
            self.ioc.write_bytes(ORIGINAL.replace(b"Static,ProducerStack,ProducerTCB", b"Dynamic,NULL,NULL"))
            self.generated.write_text(generated(dynamic=True), encoding="utf-8")
        with patch.object(a, "doctor", return_value=self.installation):
            return a.make_plan(self.project, self.ioc, self.xml, "Unit", [self.source], ["Producer=384"], ["Samples=16"], self.tools)

    def materialize(self, plan, dynamic=False):
        self.ioc.write_bytes(a.edit_ioc(self.ioc.read_bytes(), plan["task_changes"], plan["queue_changes"]))
        self.generated.write_text(generated(384, 16, dynamic), encoding="utf-8")
        self.map.write_text(fake_map(384, 16, dynamic), encoding="utf-8")

    def simulated_native_success(self, plan, command, cwd, log, env, timeout=360, record=None, build_rc=0):
        """Synthetic compiler products exercise checks; never native-build evidence."""
        log.write_text("synthetic process output", encoding="utf-8")
        if "-jar" in command:
            self.materialize(plan)
        else:
            (log.parent / "keil.log").write_text("*** Using Compiler 'V5.06 update 7 (build 960)'\ncompiling user_app.c...\n0 Error(s), 2 Warning(s)\n", encoding="utf-8")
            self.map.write_text(fake_map(384, 16), encoding="utf-8")
            self.map.with_suffix(".axf").write_bytes(b"synthetic image")
        result = record if record is not None else {}
        result.update(status="EXITED", exit_code=0 if "-jar" in command else build_rc,
                      timeout_seconds=timeout)
        return result

    def test_only_requested_numeric_fields_change_and_crlf_preserved(self):
        data = ORIGINAL.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        expected = data.replace(b"Producer,24,256,", b"Producer,24,384,").replace(b"Samples,8,uint32_t", b"Samples,16,uint32_t")
        self.assertEqual(a.edit_ioc(data, {"Producer": 384}, {"Samples": 16}), expected)

    def test_named_edits_do_not_depend_on_task_order(self):
        data = (ROOT / "examples/cubemx-rtos/adapter-fixture-b/telemetry_fixture.ioc").read_bytes()
        result = a.parse_ioc(a.edit_ioc(data, {"Logger": 448}, {"Frames": 20}))
        self.assertEqual([(t["name"], t["stack_words"]) for t in result["tasks"]], [("Logger", 448), ("Sampler", 192)])
        self.assertEqual(result["queues"][0]["capacity_elements"], 20)

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(a.AdapterError):
            a.parse_ioc(ORIGINAL + b"\nFREERTOS.Tasks01=x\n")

    def test_duplicate_names_rejected(self):
        with self.assertRaises(a.AdapterError):
            a.parse_ioc(ORIGINAL.replace(b";Consumer,", b";Producer,"))

    def test_unknown_fields_versions_and_shapes_rejected(self):
        for data in (ORIGINAL + b"\nFREERTOS.Tasks02=Extra\n", ORIGINAL.replace(b"6.18.1", b"6.19.0"),
                     ORIGINAL.replace(b"uint32_t,0,Static", b"uint16_t,0,Static"),
                     ORIGINAL.replace(b"ProducerStack,ProducerTCB", b"ProducerStack,ProducerTCB,EXTRA")):
            with self.subTest(data=data[-40:]), self.assertRaises(a.AdapterError):
                a.parse_ioc(data)

    def test_bad_requested_names_units_and_duplicates(self):
        tasks = a.parse_ioc(ORIGINAL)["tasks"]
        for edits in (["Missing=300"], ["Producer=300", "Producer=400"], ["Producer=0"], ["Producer=4294967295"], ["Producer=256"]):
            with self.subTest(edits=edits), self.assertRaises(a.AdapterError):
                a.assignments(edits, tasks, "stack_words")

    def test_plan_id_and_single_use_source_snapshot(self):
        plan = self.plan()
        receipt = self.root / "plan.json"
        a.write_json(receipt, plan)
        self.assertEqual(a.load_plan(receipt)["plan_id"], plan["plan_id"])
        plan["queue_changes"]["Samples"] = 99
        a.write_json(receipt, plan)
        with self.assertRaises(a.AdapterError):
            a.load_plan(receipt)

    def test_all_project_source_drift_rejected_before_tool_execution(self):
        for relative in ("rtos_ownership.ioc", ".mxproject", "MDK-ARM/rtos_ownership.uvprojx", "APP/app.h"):
            with self.subTest(relative=relative):
                plan = self.plan()
                path = self.project / relative
                before = path.read_bytes()
                path.write_bytes(before + b"\nmanual edit\n")
                with patch.object(a, "doctor") as doctor, patch.object(a, "run") as run:
                    with self.assertRaises(a.AdapterError):
                        a.apply_plan(plan, self.root, self.root / "unused")
                    doctor.assert_not_called()
                    run.assert_not_called()
                path.write_bytes(before)

    def test_generation_zero_exit_missing_or_stale_products_rejected(self):
        log = self.root / "generate.log"
        log.write_text("finished", encoding="utf-8")
        with self.assertRaises(a.AdapterError):
            a.check_generation({"exit_code": 0}, log, [self.root / "missing.c"], time.time_ns(), None)
        with self.assertRaises(a.AdapterError):
            a.check_generation({"exit_code": 0}, log, [self.generated], time.time_ns(), a.sha(self.generated))

    def test_build_zero_exit_without_summary_or_products_rejected(self):
        log = self.root / "build.log"
        for content in ("", "0 Error(s), 0 Warning(s)"):
            log.write_text(content, encoding="utf-8")
            with self.assertRaises(a.AdapterError):
                a.check_build({"exit_code": 0}, log, self.map, self.root / "missing.axf", time.time_ns())

    def test_static_and_dynamic_output_verification(self):
        for dynamic in (False, True):
            with self.subTest(dynamic=dynamic):
                self.ioc.write_bytes(ORIGINAL)
                plan = self.plan(dynamic)
                self.materialize(plan, dynamic)
                self.assertEqual(a.verify_outputs(plan, self.map)["runtime"], "NOT_RUN")

    def test_first_task_weak_fallback_cannot_pass(self):
        plan = self.plan()
        self.materialize(plan)
        self.map.write_text(fake_map(384, 16).replace("user_app.o(i.Producer_Entry)", "app_freertos.o(i.Producer_Entry)"), encoding="utf-8")
        with self.assertRaisesRegex(a.AdapterError, "expected user object"):
            a.verify_outputs(plan, self.map)

    def test_missing_second_entry_cannot_pass(self):
        plan = self.plan()
        self.materialize(plan)
        self.map.write_text("\n".join(line for line in fake_map(384, 16).splitlines() if "Consumer_Entry" not in line), encoding="utf-8")
        with self.assertRaisesRegex(a.AdapterError, "expected user object"):
            a.verify_outputs(plan, self.map)

    def test_duplicate_creation_wrong_binding_and_map_size_rejected(self):
        plan = self.plan()
        self.materialize(plan)
        good = self.generated.read_text(encoding="utf-8")
        for text in (good + "ProducerHandle = osThreadNew(Producer_Entry, NULL, &Producer_attributes);\n",
                     good.replace("&Producer_attributes);", "&Consumer_attributes);"),
                     good.replace(".stack_mem=&ProducerStack[0]", ".stack_mem=&ConsumerStack[0]")):
            self.generated.write_text(text, encoding="utf-8")
            with self.assertRaises(a.AdapterError):
                a.verify_outputs(plan, self.map)
        self.generated.write_text(good, encoding="utf-8")
        self.map.write_text(fake_map(384, 16).replace("Data 1536", "Data 384"), encoding="utf-8")
        with self.assertRaisesRegex(a.AdapterError, "byte size mismatch"):
            a.verify_outputs(plan, self.map)

    def test_nonempty_enabled_hook_and_escaping_paths_rejected(self):
        original = self.xml.read_text(encoding="utf-8")
        for bad in (original.replace("<UserProg1Name />", "<UserProg1Name>danger.exe</UserProg1Name>"),
                    original.replace("<OutputDirectory>out</OutputDirectory>", "<OutputDirectory>../../outside</OutputDirectory>"),
                    original.replace("../APP;../Core/Inc", "../../outside")):
            self.xml.write_text(bad, encoding="utf-8")
            with self.assertRaises(a.AdapterError):
                self.plan()
        self.xml.write_text(original, encoding="utf-8")
        (self.project / ".mxproject").write_text("[PreviousLibFiles]\nLibFiles=../outside.c;\n", encoding="utf-8")
        with self.assertRaises(a.AdapterError):
            self.plan()

    def test_missing_or_duplicate_user_source_rejected(self):
        original = self.source.read_text(encoding="utf-8")
        self.source.write_text("void Consumer_Entry(void *argument) {}", encoding="utf-8")
        with self.assertRaisesRegex(a.AdapterError, "user definition"):
            self.plan()
        self.source.write_text(original, encoding="utf-8")
        xml = self.xml.read_text(encoding="utf-8")
        xml = xml.replace("</Files>", "<File><FileName>user_app.c</FileName><FileType>1</FileType><FilePath>../APP/user_app.c</FilePath></File></Files>")
        self.xml.write_text(xml, encoding="utf-8")
        with self.assertRaisesRegex(a.AdapterError, "more than once"):
            self.plan()

    def test_partial_apply_failure_keeps_backup_logs_and_failure_receipt(self):
        plan = self.plan()
        reports = self.root / "failed-apply"
        def fake_run(command, cwd, log, env, timeout=600, record=None):
            log.write_text("synthetic zero exit without generated updates", encoding="utf-8")
            return {"exit_code": 0}
        with patch.object(a, "doctor", return_value=self.installation), patch.object(a, "run", side_effect=fake_run):
            with self.assertRaises(a.AdapterError):
                a.apply_plan(plan, self.root, reports)
        self.assertEqual((reports / "source-before.ioc").read_bytes(), ORIGINAL)
        self.assertTrue((reports / "cubemx.log").is_file())
        self.assertEqual(json.loads((reports / "result.json").read_text(encoding="utf-8"))["status"], "FAILED")
        self.assertNotEqual(self.ioc.read_bytes(), ORIGINAL)

    def test_atomic_json_failure_keeps_previous_complete_record(self):
        path = self.root / "result.json"
        a.write_json(path, {"status": "BEFORE"})
        with patch.object(a.os, "replace", side_effect=OSError("replace blocked")):
            with self.assertRaises(OSError):
                a.write_json(path, {"status": "AFTER"})
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "BEFORE"})
        self.assertEqual(list(self.root.glob("result.json.*.tmp")), [])

    def test_timeout_records_real_exit_and_cleans_owned_process(self):
        log = self.root / "timeout.log"
        with self.assertRaises(subprocess.TimeoutExpired):
            a.run([sys.executable, "-B", "-c", "import time; print('started', flush=True); time.sleep(30)"],
                  self.root, log, os.environ.copy(), timeout=0.4)
        receipt = json.loads(log.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "TIMEOUT")
        self.assertIsInstance(receipt["exit_code"], int)
        self.assertEqual(receipt["cleanup"]["status"], "COMPLETE")
        self.assertEqual(receipt["cleanup"]["pid"], receipt["pid"])

    def test_interrupt_records_cleanup_and_reraises(self):
        process = MagicMock()
        process.pid = 456
        process.wait.side_effect = KeyboardInterrupt()
        process.poll.return_value = -9
        log = self.root / "interrupt.log"
        with patch.object(a.subprocess, "Popen", return_value=process), patch.object(a, "stop_owned_process", return_value={"status": "COMPLETE", "pid": 456}) as cleanup:
            with self.assertRaises(KeyboardInterrupt):
                a.run(["synthetic-tool"], self.root, log, os.environ.copy())
            cleanup.assert_called_once_with(process)
        record = json.loads(log.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "INTERRUPTED")
        self.assertEqual(record["exit_code"], -9)

    def test_checkpoint_io_failure_after_launch_cleans_owned_process(self):
        log = self.root / "checkpoint-fault.log"
        original = a.write_json
        count = 0
        def fail_second(path, value):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError("checkpoint write failed after launch")
            original(path, value)
        with patch.object(a, "write_json", side_effect=fail_second):
            with self.assertRaises(OSError):
                a.run([sys.executable, "-B", "-c", "import time; time.sleep(30)"], self.root, log, os.environ.copy())
        record = json.loads(log.with_suffix(".json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "FAILED")
        self.assertEqual(record["cleanup"]["status"], "COMPLETE")
        self.assertIsInstance(record["exit_code"], int)

    def test_preexisting_application_creation_rejected_before_plan(self):
        self.source.write_text(self.source.read_text(encoding="utf-8") + "void Other(void) { osThreadNew(Producer_Entry, NULL, 0); }\n", encoding="utf-8")
        with self.assertRaisesRegex(a.AdapterError, "outside generated owner"):
            self.plan()

    def test_linked_vendor_inputs_refused_even_under_supplied_vendor_root(self):
        vendor = self.root / "vendor"
        vendor.mkdir()
        external = vendor / "outside.c"
        external.write_text("void outside(void) {}\n", encoding="utf-8")
        original = self.xml.read_text(encoding="utf-8")
        for bad in (original.replace("../Core/Src/app_freertos.c", str(external)),
                    original.replace("../APP;../Core/Inc", str(vendor)),
                    original.replace("</TargetCommonOption>", f"<ScatterFile>{external}</ScatterFile></TargetCommonOption>")):
            self.xml.write_text(bad, encoding="utf-8")
            with self.assertRaisesRegex(a.AdapterError, "escapes allowed roots"):
                a.inspect_project(self.project, self.ioc, self.xml, "Unit", [self.source], [vendor])
        self.xml.write_text(original, encoding="utf-8")
        self.ioc.write_bytes(ORIGINAL.replace(b"ProjectManager.LibraryCopy=0", b"ProjectManager.LibraryCopy=1"))
        with self.assertRaisesRegex(a.AdapterError, "LibraryCopy"):
            self.plan()

    def test_conflicting_allocation_macro_rejected(self):
        plan = self.plan()
        self.materialize(plan)
        config = self.project / "Core/Inc/FreeRTOSConfig.h"
        config.write_text(config.read_text(encoding="utf-8") + "#define configSUPPORT_STATIC_ALLOCATION 0\n", encoding="utf-8")
        with self.assertRaisesRegex(a.AdapterError, "defined exactly once"):
            a.verify_outputs(plan, self.map)

    def test_source_changed_during_successful_rebuild_cannot_pass(self):
        plan = self.plan()
        reports = self.root / "during-build-drift"
        def fake_run(command, cwd, log, env, timeout=360, record=None):
            if "-jar" in command:
                log.write_text("synthetic native generation", encoding="utf-8")
                self.materialize(plan)
            else:
                log.write_text("process finished", encoding="utf-8")
                (reports / "keil.log").write_text("*** Using Compiler 'V5.06 update 7 (build 960)'\ncompiling user_app.c...\n0 Error(s), 0 Warning(s)\n", encoding="utf-8")
                self.map.write_text(fake_map(384, 16), encoding="utf-8")
                self.map.with_suffix(".axf").write_bytes(b"test image built before manual source edit")
                (self.project / "Core/Src/main.c").write_text("int main(void) { return 42; }\n", encoding="utf-8")
            return {"exit_code": 0}
        with patch.object(a, "doctor", return_value=self.installation), patch.object(a, "run", side_effect=fake_run):
            with self.assertRaisesRegex(a.AdapterError, "inputs changed during rebuild"):
                a.apply_plan(plan, self.root, reports)
        result = json.loads((reports / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["build"]["status"], "FAILED")
        self.assertEqual(result["build"]["exit_code"], 0)
        self.assertEqual(result["verification"]["status"], "NOT_RUN")

    def test_apply_start_failure_has_terminal_summary_and_unstarted_null_code(self):
        plan = self.plan()
        reports = self.root / "launch-failure"
        native_run = a.run
        def fail_start(command, cwd, log, env, timeout=360, record=None):
            return native_run([str(self.root / "missing-tool.exe")], cwd, log, env, timeout, record)
        with patch.object(a, "doctor", return_value=self.installation), patch.object(a, "run", side_effect=fail_start):
            with self.assertRaises(OSError):
                a.apply_plan(plan, self.root, reports, timeout=2.5)
        result = json.loads((reports / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["generation"]["status"], "FAILED")
        self.assertEqual(result["failure_type"], "process_start")
        self.assertEqual(result["failure_stage"], "generate")
        self.assertIsNone(result["actual_exit_code"])
        self.assertIsNone(result["generation"]["exit_code"])
        self.assertEqual(result["generation"]["timeout_seconds"], 2.5)
        self.assertEqual(result["build"], {"status": "NOT_RUN", "exit_code": None})
        self.assertEqual(result["verification"]["status"], "NOT_RUN")

    def test_apply_timeout_propagates_real_process_cleanup_and_preserves_partial_log(self):
        plan = self.plan()
        reports = self.root / "apply-timeout"
        native_run = a.run
        def timeout_process(command, cwd, log, env, timeout=360, record=None):
            return native_run([sys.executable, "-B", "-u", "-c", "import time; print('partial'); time.sleep(30)"],
                              cwd, log, env, timeout, record)
        with patch.object(a, "doctor", return_value=self.installation), patch.object(a, "run", side_effect=timeout_process):
            with self.assertRaises(subprocess.TimeoutExpired):
                a.apply_plan(plan, self.root, reports, timeout=0.5)
        result = json.loads((reports / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["terminal_state"], "TIMEOUT")
        self.assertEqual(result["generation"]["status"], "TIMEOUT")
        self.assertEqual(result["failure_type"], "timeout")
        self.assertIsInstance(result["actual_exit_code"], int)
        self.assertEqual(result["actual_exit_code"], result["generation"]["exit_code"])
        self.assertEqual(result["cleanup"]["status"], "COMPLETE")
        self.assertIn("partial", (reports / "cubemx.log").read_text(encoding="utf-8"))
        self.assertEqual(result["build"]["status"], "NOT_RUN")

    def test_apply_interrupt_records_terminal_state_and_cli_returns_130(self):
        plan = self.plan()
        plan_path = self.root / "plan.json"
        a.write_json(plan_path, plan)
        reports = self.root / "interrupted-apply"
        process = MagicMock()
        process.pid = 789
        process.wait.side_effect = KeyboardInterrupt()
        process.poll.return_value = -9
        with patch.object(a, "doctor", return_value=self.installation), \
             patch.object(a.subprocess, "Popen", return_value=process), \
             patch.object(a, "stop_owned_process", return_value={"status": "COMPLETE", "pid": 789}), \
             contextlib.redirect_stderr(io.StringIO()):
            code = a.main(["apply", "--plan", str(plan_path), "--work-root", str(self.root), "--reports", str(reports)])
        self.assertEqual(code, 130)
        result = json.loads((reports / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["terminal_state"], "INTERRUPTED")
        self.assertEqual(result["generation"]["status"], "INTERRUPTED")
        self.assertEqual(result["actual_exit_code"], -9)
        self.assertEqual(result["build"]["status"], "NOT_RUN")

    def test_apply_build_postcheck_failure_keeps_exit_code_and_completed_generation(self):
        plan = self.plan()
        reports = self.root / "build-postcheck"
        def bad_build(command, cwd, log, env, timeout=360, record=None):
            result = self.simulated_native_success(plan, command, cwd, log, env, timeout, record)
            if "-jar" not in command:
                self.map.unlink()
            return result
        with patch.object(a, "doctor", return_value=self.installation), patch.object(a, "run", side_effect=bad_build):
            with self.assertRaisesRegex(a.AdapterError, "Missing build product"):
                a.apply_plan(plan, self.root, reports)
        result = json.loads((reports / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["generation"]["terminal_state"], "PASS")
        self.assertEqual(result["build"]["status"], "FAILED")
        self.assertEqual(result["build"]["process_status"], "EXITED")
        self.assertEqual(result["actual_exit_code"], 0)
        self.assertEqual(result["failure_type"], "validation")
        self.assertEqual(result["verification"]["status"], "NOT_RUN")

    def test_apply_zero_error_keil_exit_one_is_still_accepted(self):
        plan = self.plan()
        reports = self.root / "keil-warning-success"
        def successful(command, cwd, log, env, timeout=360, record=None):
            return self.simulated_native_success(plan, command, cwd, log, env, timeout, record, build_rc=1)
        with patch.object(a, "doctor", return_value=self.installation), patch.object(a, "run", side_effect=successful):
            result = a.apply_plan(plan, self.root, reports, timeout=7)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["build"]["status"], "EXITED")
        self.assertEqual(result["build"]["exit_code"], 1)
        self.assertEqual(result["build"]["errors"], 0)
        self.assertEqual(result["build"]["warnings"], 2)
        self.assertEqual(result["build"]["terminal_state"], "PASS")
        self.assertEqual(result["build"]["timeout_seconds"], 7)

    def test_apply_wrong_process_exit_cannot_pass_a_zero_error_build_summary(self):
        plan = self.plan()
        reports = self.root / "wrong-exit"
        def wrong_exit(command, cwd, log, env, timeout=360, record=None):
            return self.simulated_native_success(plan, command, cwd, log, env, timeout, record, build_rc=2)
        with patch.object(a, "doctor", return_value=self.installation), patch.object(a, "run", side_effect=wrong_exit):
            with self.assertRaisesRegex(a.AdapterError, "Keil rebuild failed"):
                a.apply_plan(plan, self.root, reports)
        result = json.loads((reports / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["generation"]["terminal_state"], "PASS")
        self.assertEqual(result["build"]["status"], "FAILED")
        self.assertEqual(result["actual_exit_code"], 2)
        self.assertEqual(result["verification"]["status"], "NOT_RUN")

    def test_apply_wrong_map_owner_fails_verification_after_completed_build(self):
        plan = self.plan()
        reports = self.root / "wrong-owner"
        def wrong_owner(command, cwd, log, env, timeout=360, record=None):
            result = self.simulated_native_success(plan, command, cwd, log, env, timeout, record)
            if "-jar" not in command:
                self.map.write_text(fake_map(384, 16).replace("user_app.o(i.Producer_Entry)",
                                    "app_freertos.o(i.Producer_Entry)"), encoding="utf-8")
            return result
        with patch.object(a, "doctor", return_value=self.installation), patch.object(a, "run", side_effect=wrong_owner):
            with self.assertRaisesRegex(a.AdapterError, "expected user object"):
                a.apply_plan(plan, self.root, reports)
        result = json.loads((reports / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["build"]["terminal_state"], "PASS")
        self.assertEqual(result["verification"]["status"], "FAILED")
        self.assertEqual(result["failure_stage"], "verify")
        self.assertIsNone(result["actual_exit_code"])
        self.assertEqual(result["build"]["exit_code"], 0)

    def test_apply_final_record_failure_returns_nonzero_without_persisting_success(self):
        plan = self.plan()
        plan_path = self.root / "plan.json"
        a.write_json(plan_path, plan)
        reports = self.root / "final-save-failed"
        original_write = a.write_json
        def blocked_final_save(path, value):
            if Path(path).name == "result.json" and value.get("status") == "PASS":
                raise OSError("final result storage unavailable")
            original_write(path, value)
        def successful(command, cwd, log, env, timeout=360, record=None):
            return self.simulated_native_success(plan, command, cwd, log, env, timeout, record)
        stderr = io.StringIO()
        with patch.object(a, "doctor", return_value=self.installation), \
             patch.object(a, "run", side_effect=successful), patch.object(a, "write_json", side_effect=blocked_final_save), \
             contextlib.redirect_stderr(stderr):
            code = a.main(["apply", "--plan", str(plan_path), "--work-root", str(self.root), "--reports", str(reports)])
        self.assertEqual(code, 1)
        self.assertIn("final result storage unavailable", stderr.getvalue())
        result = json.loads((reports / "result.json").read_text(encoding="utf-8"))
        self.assertNotEqual(result["status"], "PASS")
        self.assertNotIn("verified_snapshot", result)

    def test_invalid_timeout_rejected_before_plan_read_or_output_creation(self):
        for value in ("0", "-1", "nan", "inf", "-inf", "bad"):
            reports = self.root / ("invalid-" + value)
            with self.subTest(value=value), patch.object(a, "load_plan") as load, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    a.main(["apply", "--plan", "missing.json", "--work-root", str(self.root),
                            "--reports", str(reports), "--timeout=" + value])
                self.assertEqual(caught.exception.code, 2)
                load.assert_not_called()
                self.assertFalse(reports.exists())

    def test_first_apply_record_failure_starts_no_process_and_preserves_ioc(self):
        plan = self.plan()
        with patch.object(a, "doctor", return_value=self.installation), \
             patch.object(a, "write_json", side_effect=OSError("disk unavailable")), patch.object(a, "run") as run:
            with self.assertRaisesRegex(OSError, "disk unavailable"):
                a.apply_plan(plan, self.root, self.root / "record-failure")
        run.assert_not_called()
        self.assertEqual(self.ioc.read_bytes(), ORIGINAL)

    def test_verify_rejects_post_build_source_edit_even_when_products_unchanged(self):
        plan = self.plan()
        self.materialize(plan)
        plan_path = self.root / "plan.json"
        a.write_json(plan_path, plan)
        reports = self.root / "applied"
        reports.mkdir()
        image = self.map.with_suffix(".axf")
        image.write_bytes(b"synthetic test product")
        a.write_json(reports / "result.json", {"status": "PASS", "plan_id": plan["plan_id"],
            "products": {"map": {"path": str(self.map), "sha256": a.sha(self.map)},
                         "axf": {"path": str(image), "sha256": a.sha(image)}},
            "verified_snapshot": a.snapshot(self.project)})
        argv = ["verify", "--plan", str(plan_path), "--reports", str(reports)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(a.main(argv), 0)
            self.source.write_text(self.source.read_text(encoding="utf-8") + "int manual_change = 1;\n", encoding="utf-8")
            self.assertEqual(a.main(argv), 1)

    def test_lexical_reparse_component_rejected_even_if_it_resolves_inside(self):
        with patch.object(a.Path, "is_symlink", return_value=True):
            with self.assertRaisesRegex(a.AdapterError, "Reparse"):
                a.checked_path(self.source, [self.project], "source")


if __name__ == "__main__":
    unittest.main()

