"""Continuous, fail-closed Tomahawk multiphysics runner.

The runner uses one CAD_A2 results folder and executes the external stages in
order: MHD -> NEUTRONICS -> CFD -> CHF. A stage is not considered complete
until its process returns zero *and* a declared output artifact exists. The
artifact is written to a handoff manifest and exposed to the next stage as
``{previous_output}`` and ``TOMAHAWK_PREVIOUS_OUTPUT``.

This is an orchestration layer. It does not contain VMEC, OpenMC/DAGMC,
NekRS, or a CHF correlation. Those programs and their real input data must
be installed/supplied by the user. Missing commands, inputs, or outputs stop
the pipeline; no synthetic physics result is produced.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time


VERSION = 'PHYSICS-RUNNER-2.0-CONTINUOUS'
STAGES = ('MHD', 'NEUTRONICS', 'CFD', 'CHF')
PIPELINE_DIR = 'Tomahawk_Continuous_Run'
CONFIG_NAME = 'Tomahawk_Continuous_Run_Config.json'
TEMPLATE_NAME = 'Tomahawk_Continuous_Run_Config.template.json'

DEFAULT_OUTPUTS = {
    'MHD': ['wout_*.nc', 'mhd_output.json', 'mhd_output.h5'],
    'NEUTRONICS': ['statepoint*.h5', 'neutronics_output.json', 'tallies*.json'],
    'CFD': ['cfd_output.json', '*.vtu', '*.vtk', '*.csv'],
    'CHF': ['chf_results.json', 'chf_results.csv'],
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def utc_now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def stage_result(name, status, reason='', command='', returncode=None,
                 elapsed_s=0.0, log='', output_path=None, handoff=None,
                 stage_dir=None):
    return {
        'stage': name,
        'status': status,
        'reason': reason,
        'command': command,
        'returncode': returncode,
        'elapsed_s': elapsed_s,
        'log': log,
        'output_path': output_path,
        'handoff_manifest': handoff,
        'stage_dir': stage_dir,
    }


def resolve_path(root, value):
    if value is None or value == '':
        return None
    path = Path(str(value))
    return path.resolve() if path.is_absolute() else (Path(root) / path).resolve()


def safe_replace(text, context):
    """Replace only known placeholders; preserve other braces in commands."""
    text = str(text)
    for key, value in context.items():
        text = text.replace('{' + str(key) + '}', str(value if value is not None else ''))
    return text


def command_tokens(command, context):
    if isinstance(command, (list, tuple)):
        return [safe_replace(item, context) for item in command]
    if not command:
        return []
    rendered = safe_replace(command, context)
    try:
        tokens = shlex.split(rendered, posix=(os.name != 'nt'))
    except ValueError as exc:
        raise ValueError('Invalid command quoting: %s' % exc)
    if os.name == 'nt':
        tokens = [
            token[1:-1] if len(token) >= 2 and token[0] == token[-1] == '"' else token
            for token in tokens
        ]
    return tokens


def command_display(tokens):
    if os.name == 'nt':
        return subprocess.list2cmdline([str(x) for x in tokens])
    return ' '.join(shlex.quote(str(x)) for x in tokens)


def choose_results_folder():
    try:
        try:
            from PySide import QtWidgets
        except ImportError:
            try:
                from PySide2 import QtWidgets
            except ImportError:
                from PySide6 import QtWidgets
        selected = QtWidgets.QFileDialog.getExistingDirectory(
            None, 'Select the CAD_A2 results folder (the folder containing build_report.json)')
        return Path(selected) if selected else None
    except ImportError:
        return None


def normalize_case_root(root, explicit_build_report=None):
    """Correct the common mistake of selecting the result folder's __pycache__."""
    root = Path(root).resolve()
    if explicit_build_report:
        return root, None
    if root.name.lower() == '__pycache__' and (root.parent / 'build_report.json').is_file():
        return root.parent, 'The selected __pycache__ directory was corrected to its CAD_A2 parent.'
    return root, None


def validate_case(root, build_report_arg=None):
    report_path = (Path(build_report_arg).resolve()
                   if build_report_arg else Path(root) / 'build_report.json')
    if not report_path.is_file():
        return {
            'status': 'BLOCKED_MISSING_BUILD_REPORT',
            'reason': 'Build report not found: %s' % report_path,
            'report': {}, 'report_path': str(report_path)
        }
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {
            'status': 'BLOCKED_INVALID_BUILD_REPORT',
            'reason': 'Could not parse %s: %s' % (report_path, exc),
            'report': {}, 'report_path': str(report_path)
        }
    if report.get('native_execution') not in {
            'COMPLETED_CONCEPT_BUILD_BOUNDARY_G1_NUMERICAL_PASS',
            'COMPLETED_WITH_FAILURES'}:
        return {
            'status': 'BLOCKED_CAD_BUILD_NOT_ACCEPTED',
            'reason': str(report.get('native_execution')),
            'report': report, 'report_path': str(report_path)
        }
    if not report.get('assembly_build_accepted', False):
        return {
            'status': 'BLOCKED_CAD_ASSEMBLY_NOT_ACCEPTED',
            'reason': 'assembly_build_accepted is false.',
            'report': report, 'report_path': str(report_path)
        }
    if report.get('failed'):
        return {
            'status': 'BLOCKED_CAD_COMPONENT_FAILURES',
            'reason': 'CAD report lists failed components.',
            'report': report, 'report_path': str(report_path)
        }
    if not report.get('g1_audit', {}).get('status', '').startswith('PASS'):
        return {
            'status': 'BLOCKED_G1_NUMERICAL_GATE',
            'reason': 'G1 audit is not PASS.',
            'report': report, 'report_path': str(report_path)
        }
    if not (Path(root) / 'Tomahawk_Multiphysics_Physics_Contract.json').is_file():
        return {
            'status': 'BLOCKED_MISSING_MULTIPHYSICS_PREP',
            'reason': 'Tomahawk_Multiphysics_Physics_Contract.json is absent.',
            'report': report, 'report_path': str(report_path)
        }
    if not (Path(root) / 'Solver_Geometry').is_dir():
        return {
            'status': 'BLOCKED_MISSING_SOLVER_GEOMETRY',
            'reason': 'Solver_Geometry directory is absent.',
            'report': report, 'report_path': str(report_path)
        }
    return {
        'status': 'READY',
        'reason': 'CAD, G1, contract, and solver geometry prerequisites are present.',
        'report': report, 'report_path': str(report_path)
    }


def required_paths(root, stage):
    geometry = Path(root) / 'Solver_Geometry'
    names = {
        'MHD': ['MHD_Plasma_Domain.step', 'MHD_Vacuum_Region.step',
                'MHD_Coil_And_Casing_Regions.step'],
        'NEUTRONICS': ['NEUTRONICS_Material_To_STEP_Map.json'],
        'CFD': ['CFD_RF_Connected_Coolant_Domains.step',
                'CFD_RF_Cassette_Solid_Regions.step',
                'CFD_RF_Named_Boundary_Seeds.json'],
        'CHF': [],
    }
    return [geometry / name for name in names.get(stage, [])]


def make_template(root):
    template = {
        'schema_version': 'TOMAHAWK-CONTINUOUS-1.0',
        'purpose': 'One-folder external solver pipeline; replace null commands and paths with real installation/data.',
        'stages': {
            'MHD': {
                'command': None,
                'inputs': {'mhd_input': 'MHD/input.toml'},
                'outputs': DEFAULT_OUTPUTS['MHD'],
                'consumes_previous_output': False,
            },
            'NEUTRONICS': {
                'command': None,
                'inputs': {
                    'dagmc': 'NEUTRONICS/dagmc.h5m',
                    'materials': 'NEUTRONICS/materials.xml',
                    'settings': 'NEUTRONICS/settings.xml',
                    'cross_sections': 'NEUTRONICS/cross_sections.xml',
                },
                'outputs': DEFAULT_OUTPUTS['NEUTRONICS'],
                'consumes_previous_output': True,
            },
            'CFD': {
                'command': None,
                'inputs': {'cfd_mesh': 'CFD/cassette.re2', 'cfd_case': 'CFD/cassette.par'},
                'outputs': DEFAULT_OUTPUTS['CFD'],
                'consumes_previous_output': True,
            },
            'CHF': {
                'command': None,
                'inputs': {'chf_results': 'CHF/chf_input.json'},
                'outputs': DEFAULT_OUTPUTS['CHF'],
                'consumes_previous_output': True,
            },
        },
    }
    path = Path(root) / TEMPLATE_NAME
    if not path.exists():
        write_json(path, template)
    return path


def load_config(root, config_arg=None):
    path = Path(config_arg).resolve() if config_arg else Path(root) / CONFIG_NAME
    if not path.is_file():
        return {}, path, make_template(root)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ValueError('Could not parse pipeline config %s: %s' % (path, exc))
    if not isinstance(data, dict):
        raise ValueError('Pipeline config must be a JSON object: %s' % path)
    return data, path, None


def cli_overrides(args):
    return {
        'MHD': {'command': args.mhd_command, 'inputs': {'mhd_input': args.mhd_input},
                'outputs': args.mhd_output},
        'NEUTRONICS': {
            'command': args.neutronics_command,
            'inputs': {'dagmc': args.dagmc, 'materials': args.materials,
                       'settings': args.settings, 'cross_sections': args.cross_sections},
            'outputs': args.neutronics_output,
        },
        'CFD': {'command': args.cfd_command,
                'inputs': {'cfd_mesh': args.cfd_mesh, 'cfd_case': args.cfd_case},
                'outputs': args.cfd_output},
        'CHF': {'command': args.chf_command,
                'inputs': {'chf_results': args.chf_results},
                'outputs': args.chf_output},
    }


def stage_specs(root, config, args):
    overrides = cli_overrides(args)
    stages = config.get('stages', {}) if isinstance(config, dict) else {}
    specs = {}
    for stage in STAGES:
        base = stages.get(stage, {}) or {}
        if not isinstance(base, dict):
            raise ValueError('%s stage configuration must be an object.' % stage)
        spec = dict(base)
        spec['command'] = overrides[stage]['command'] or spec.get('command')
        inputs = dict(spec.get('inputs', {}) or {})
        for key, value in overrides[stage]['inputs'].items():
            if value:
                inputs[key] = str(value)
        spec['inputs'] = inputs
        outputs = overrides[stage]['outputs'] or spec.get('outputs')
        spec['outputs'] = outputs or DEFAULT_OUTPUTS[stage]
        spec['consumes_previous_output'] = bool(spec.get('consumes_previous_output', stage != 'MHD'))
        specs[stage] = spec
    return specs


def normalize_outputs(outputs):
    if isinstance(outputs, str):
        return [outputs]
    if isinstance(outputs, (list, tuple)):
        return [str(x) for x in outputs if str(x)]
    return []


def snapshot_declared_outputs(stage_dir, patterns):
    """Record existing declared outputs so stale files cannot satisfy a rerun."""
    snapshot = {}
    for pattern in normalize_outputs(patterns):
        path = Path(pattern)
        if path.is_absolute():
            matches = [path] if path.exists() else list(path.parent.glob(path.name))
        else:
            matches = list(Path(stage_dir).glob(pattern))
        for item in matches:
            if item.exists():
                stat = item.stat()
                snapshot[str(item.resolve())] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def find_declared_output(stage_dir, patterns, before=None):
    candidates = []
    for pattern in normalize_outputs(patterns):
        path = Path(pattern)
        if path.is_absolute():
            if path.exists():
                matches = [path]
            else:
                matches = list(path.parent.glob(path.name))
        else:
            matches = list(Path(stage_dir).glob(pattern))
        for item in matches:
            if item.exists() and item.name not in {
                    'stdout_stderr.log', 'stage_input_manifest.json',
                    'stage_output_manifest.json'}:
                resolved = item.resolve()
                if before is not None:
                    stat = resolved.stat()
                    old = before.get(str(resolved))
                    if old is not None and old == (stat.st_mtime_ns, stat.st_size):
                        continue
                candidates.append(resolved)
    if not candidates:
        return None
    unique = {str(item): item for item in candidates}
    return max(unique.values(), key=lambda item: item.stat().st_mtime)


def input_paths(root, spec):
    resolved = {}
    for key, value in (spec.get('inputs', {}) or {}).items():
        if value is None or value == '':
            continue
        path = resolve_path(root, value)
        resolved[key] = path
    return resolved


def check_inputs(root, stage, resolved_inputs):
    missing = [str(path) for path in required_paths(root, stage) if not path.is_file()]
    for key, path in resolved_inputs.items():
        if not path.is_file():
            missing.append('%s=%s' % (key, path))
    return missing


def write_input_manifest(stage_dir, root, stage, resolved_inputs, previous_output):
    payload = {
        'pipeline_version': VERSION,
        'stage': stage,
        'case_root': str(Path(root).resolve()),
        'inputs': {key: str(path) for key, path in resolved_inputs.items()},
        'previous_output': str(previous_output) if previous_output else None,
        'upstream_stage': STAGES[STAGES.index(stage) - 1] if stage != STAGES[0] else None,
        'handoff_contract': 'The next stage must consume previous_output explicitly or via TOMAHAWK_PREVIOUS_OUTPUT.',
    }
    path = Path(stage_dir) / 'stage_input_manifest.json'
    write_json(path, payload)
    return path


def execute_process(stage, tokens, stage_dir, env, timeout_s):
    if not tokens:
        return stage_result(stage, 'BLOCKED_COMMAND_NOT_SUPPLIED',
                            'No external solver command was configured.')
    stage_dir = Path(stage_dir)
    stage_dir.mkdir(parents=True, exist_ok=True)
    log_path = stage_dir / 'stdout_stderr.log'
    display = command_display(tokens)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [str(token) for token in tokens], cwd=str(stage_dir), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            timeout=(timeout_s or None), check=False)
        output = completed.stdout or ''
        log_path.write_text(output, encoding='utf-8')
        if output:
            print('[%s] solver output:\n%s' % (stage, output.rstrip()), flush=True)
        status = 'EXECUTED_PASS' if completed.returncode == 0 else 'EXECUTED_FAIL'
        return stage_result(stage, status, '', display, completed.returncode,
                            time.perf_counter() - started, str(log_path))
    except FileNotFoundError as exc:
        log_path.write_text(str(exc), encoding='utf-8')
        return stage_result(stage, 'BLOCKED_EXECUTABLE_NOT_FOUND', str(exc), display,
                            None, time.perf_counter() - started, str(log_path))
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout if isinstance(exc.stdout, str) else ''
        log_path.write_text(output + '\nTIMEOUT\n', encoding='utf-8')
        return stage_result(stage, 'EXECUTED_TIMEOUT', 'Timeout exceeded.', display,
                            None, time.perf_counter() - started, str(log_path))
    except OSError as exc:
        log_path.write_text(str(exc), encoding='utf-8')
        return stage_result(stage, 'BLOCKED_PROCESS_START', str(exc), display,
                            None, time.perf_counter() - started, str(log_path))


def run_pipeline(root, args, config, config_path, validation, root_correction=None):
    root = Path(root).resolve()
    run_dir = (Path(args.output_folder).resolve()
               if args.output_folder else root / PIPELINE_DIR)
    run_dir.mkdir(parents=True, exist_ok=True)
    specs = stage_specs(root, config, args)
    report = {
        'runner_version': VERSION,
        'results_folder': str(root),
        'pipeline_folder': str(run_dir),
        'started_utc': utc_now(),
        'validation_status': validation['status'],
        'validation_reason': validation['reason'],
        'root_correction': root_correction,
        'build_report': validation.get('report_path'),
        'native_build_execution': validation.get('report', {}).get('native_execution'),
        'new_physics_run': False,
        'stages': {},
        'config': str(config_path),
        'limitations': [
            'A zero return code means the external program completed, not that its physics is validated.',
            'Each stage must declare a real output artifact before the next stage is allowed to start.',
            'Mesh convergence, conservation, material qualification, and comparison to measurements remain required.',
        ],
    }
    if validation['status'] != 'READY':
        for stage in STAGES:
            report['stages'][stage] = stage_result(stage, validation['status'], validation['reason'])
        report['overall_status'] = validation['status']
        report['elapsed_s'] = 0.0
        write_json(run_dir / 'physics_run_report.json', report)
        return report, 2

    preflight_errors = []
    resolved_by_stage = {}
    tokens_by_stage = {}
    for stage in STAGES:
        spec = specs[stage]
        inputs = input_paths(root, spec)
        resolved_by_stage[stage] = inputs
        try:
            tokens = command_tokens(spec.get('command'), {})
        except ValueError as exc:
            tokens = []
            preflight_errors.append('%s: %s' % (stage, exc))
        tokens_by_stage[stage] = tokens
        if not tokens:
            preflight_errors.append('%s: command not configured.' % stage)
        preflight_errors.extend('%s: missing %s' % (stage, item)
                                for item in check_inputs(root, stage, inputs))
        if stage != 'MHD' and not bool(spec.get('consumes_previous_output')):
            preflight_errors.append('%s: consumes_previous_output must be true.' % stage)
    if preflight_errors:
        template = make_template(root)
        for stage in STAGES:
            reason = '; '.join(item for item in preflight_errors if item.startswith(stage + ':'))
            report['stages'][stage] = stage_result(
                stage, 'BLOCKED_PIPELINE_INPUTS_OR_COMMANDS', reason or 'See pipeline_errors.',
                command_display(tokens_by_stage[stage]) if tokens_by_stage[stage] else '')
        report['pipeline_errors'] = preflight_errors
        report['template_config'] = str(template)
        report['overall_status'] = 'BLOCKED_PIPELINE_INPUTS_OR_COMMANDS'
        report['elapsed_s'] = 0.0
        write_json(run_dir / 'physics_run_report.json', report)
        return report, 2

    if args.preflight:
        # Dry-run path: report readiness without launching a single process.
        for stage in STAGES:
            tokens = tokens_by_stage[stage]
            report['stages'][stage] = stage_result(
                stage, 'PREFLIGHT_READY_NOT_LAUNCHED',
                'Inputs and command are present; external solver was not launched.',
                command_display(tokens), stage_dir=str(run_dir / ('%02d_%s' % (
                    STAGES.index(stage) + 1, stage))))
        report['overall_status'] = 'PREFLIGHT_COMPLETE_SOLVER_INPUTS_READY'
        report['completed_stages'] = []
        report['elapsed_s'] = 0.0
        write_json(run_dir / 'physics_run_report.json', report)
        return report, 0

    previous_output = None
    handoffs = {}
    for index, stage in enumerate(STAGES, 1):
        spec = specs[stage]
        stage_dir = run_dir / ('%02d_%s' % (index, stage))
        stage_dir.mkdir(parents=True, exist_ok=True)
        input_manifest = write_input_manifest(
            stage_dir, root, stage, resolved_by_stage[stage], previous_output)
        context = {
            'case_root': root,
            'stage_dir': stage_dir,
            'pipeline_dir': run_dir,
            'previous_output': previous_output or '',
            'input_manifest': input_manifest,
        }
        for key, path in resolved_by_stage[stage].items():
            context[key] = path
        for prior_stage, prior_output in handoffs.items():
            context[prior_stage.lower() + '_output'] = prior_output
        try:
            tokens = command_tokens(spec.get('command'), context)
        except ValueError as exc:
            result = stage_result(stage, 'BLOCKED_INVALID_COMMAND', str(exc), stage_dir=str(stage_dir))
            report['stages'][stage] = result
            break
        if stage != 'MHD':
            if ('{previous_output}' not in str(spec.get('command'))
                    and not bool(spec.get('consumes_previous_output_via_manifest'))):
                result = stage_result(
                    stage, 'BLOCKED_UPSTREAM_NOT_WIRED',
                    'Command must reference {previous_output}, or set consumes_previous_output_via_manifest=true.',
                    command_display(tokens), stage_dir=str(stage_dir))
                report['stages'][stage] = result
                break
        env = os.environ.copy()
        env.update({
            'TOMAHAWK_CASE_ROOT': str(root),
            'TOMAHAWK_PIPELINE_DIR': str(run_dir),
            'TOMAHAWK_STAGE': stage,
            'TOMAHAWK_STAGE_DIR': str(stage_dir),
            'TOMAHAWK_PREVIOUS_OUTPUT': str(previous_output or ''),
            'TOMAHAWK_INPUT_MANIFEST': str(input_manifest),
        })
        for prior_stage, prior_output in handoffs.items():
            env['TOMAHAWK_%s_OUTPUT' % prior_stage] = str(prior_output)
        output_snapshot = snapshot_declared_outputs(stage_dir, spec.get('outputs'))
        result = execute_process(stage, tokens, stage_dir, env, args.timeout_s)
        if result['status'] != 'EXECUTED_PASS':
            report['stages'][stage] = result
            break
        output_path = find_declared_output(stage_dir, spec.get('outputs'), output_snapshot)
        if output_path is None:
            result['status'] = 'EXECUTED_FAIL_OUTPUT_MISSING'
            result['reason'] = 'Process returned zero, but no declared output matched: %s' % normalize_outputs(spec.get('outputs'))
            report['stages'][stage] = result
            break
        output_manifest = stage_dir / 'stage_output_manifest.json'
        handoff = {
            'pipeline_version': VERSION,
            'stage': stage,
            'output_path': str(output_path),
            'output_sha256': sha(output_path) if output_path.is_file() else None,
            'output_is_file': output_path.is_file(),
            'source_log': result.get('log'),
            'created_utc': utc_now(),
        }
        write_json(output_manifest, handoff)
        result['output_path'] = str(output_path)
        result['handoff_manifest'] = str(output_manifest)
        result['stage_dir'] = str(stage_dir)
        report['stages'][stage] = result
        handoffs[stage] = output_path
        previous_output = output_path
        print('[%s] PASS; handoff -> %s' % (stage, output_path), flush=True)

    report['new_physics_run'] = any(
        str(item.get('status', '')).startswith('EXECUTED_')
        for item in report['stages'].values())
    completed = all(report['stages'].get(stage, {}).get('status') == 'EXECUTED_PASS'
                    for stage in STAGES)
    report['overall_status'] = 'CONTINUOUS_PIPELINE_COMPLETE' if completed else 'CONTINUOUS_PIPELINE_STOPPED'
    report['completed_stages'] = [stage for stage in STAGES
                                  if report['stages'].get(stage, {}).get('status') == 'EXECUTED_PASS']
    report['elapsed_s'] = sum(float(item.get('elapsed_s') or 0.0)
                              for item in report['stages'].values())
    write_json(run_dir / 'physics_run_report.json', report)
    return report, 0 if completed else 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-folder', type=Path,
                        help='CAD_A2 folder containing build_report.json and Solver_Geometry/.')
    parser.add_argument('--build-report', type=Path)
    parser.add_argument('--config', type=Path,
                        help='One JSON pipeline config; default is results-folder/' + CONFIG_NAME)
    parser.add_argument('--mhd-command'); parser.add_argument('--mhd-input', type=Path)
    parser.add_argument('--mhd-output', action='append')
    parser.add_argument('--neutronics-command'); parser.add_argument('--dagmc', type=Path)
    parser.add_argument('--materials', type=Path); parser.add_argument('--settings', type=Path)
    parser.add_argument('--cross-sections', type=Path); parser.add_argument('--neutronics-output', action='append')
    parser.add_argument('--cfd-command'); parser.add_argument('--cfd-mesh', type=Path)
    parser.add_argument('--cfd-case', type=Path); parser.add_argument('--cfd-output', action='append')
    parser.add_argument('--chf-command'); parser.add_argument('--chf-results', type=Path)
    parser.add_argument('--chf-output', action='append')
    parser.add_argument('--output-folder', type=Path)
    parser.add_argument('--timeout-s', type=int, default=0)
    parser.add_argument('--interactive', action='store_true',
                        help='Choose the CAD_A2 folder in a FreeCAD/PySide dialog.')
    parser.add_argument('--continuous', action='store_true',
                        help='Run MHD -> neutronics -> CFD -> CHF in one continuous pipeline.')
    parser.add_argument('--preflight', action='store_true',
                        help='Validate the case/config without launching external solvers.')
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    implicit_freecad = not raw_argv and 'FreeCAD' in sys.modules
    args = parser.parse_args(raw_argv)
    if args.interactive or implicit_freecad:
        selected = choose_results_folder()
        if selected is None:
            print('No CAD_A2 folder selected; cancelled.')
            return 2
        args.results_folder = selected
        args.continuous = not args.preflight
    if args.results_folder is None:
        parser.error('--results-folder is required (or use --interactive from FreeCAD).')
    root, correction = normalize_case_root(args.results_folder, args.build_report)
    try:
        config, config_path, template = load_config(root, args.config)
        validation = validate_case(root, args.build_report)
        report, code = run_pipeline(root, args, config, config_path,
                                    validation, correction)
        if args.preflight:
            for stage in report.get('stages', {}).values():
                if stage.get('status') == 'EXECUTED_PASS':
                    stage['status'] = 'PREFLIGHT_READY_NOT_LAUNCHED'
            report['new_physics_run'] = False
            if report.get('overall_status') == 'CONTINUOUS_PIPELINE_COMPLETE':
                report['overall_status'] = 'PREFLIGHT_COMPLETE_SOLVER_INPUTS_READY'
            write_json(Path(report['pipeline_folder']) / 'physics_run_report.json', report)
        print(json.dumps(report, indent=2))
        return 0 if code == 0 else 2
    except ValueError as exc:
        print('BLOCKED_CONFIGURATION: %s' % exc)
        return 2


if __name__ == '__main__':
    sys.exit(main())
