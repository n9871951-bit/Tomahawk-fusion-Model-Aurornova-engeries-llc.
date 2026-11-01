"""Run the fixed-profile thermal-response screen and numerical checks."""
from pathlib import Path
import argparse
import csv
import json
import os
import subprocess
import sys

import numpy as np
import scipy

from thermal_model import ThermalModel, reactivity, scenarios

ROOT = Path(__file__).resolve().parent


def native_run(executable, model, directory, initial, duration, offset=0.0):
    directory.mkdir(parents=True, exist_ok=True)
    s = model.settings
    count = round(duration / s['output_dt_s'])
    if not np.isclose(count * s['output_dt_s'], duration):
        raise ValueError('Native duration must be a multiple of the output interval')
    options = {
        'profile': str((ROOT / 'inputs/radial_profile.csv').resolve()),
        'csv': str((directory / 'trajectory.csv').resolve()),
        'tau_e': s['tau_E_s'], 'sync_mw': s['synchrotron_baseline_MW'],
        'sync_exponent': s['synchrotron_temperature_exponent'],
        'external_mw': s['absorbed_external_MW'], 'alpha_retention': s['alpha_retention'],
        'delay_exponent': s['alpha_delay_temperature_exponent'],
        'initial_w': initial[0], 'initial_a': initial[1],
        'initial_ein': initial[2], 'initial_eout': initial[3],
        'time_offset': offset,
        'scale_min': s['temperature_scale_min'], 'scale_max': s['temperature_scale_max'],
    }
    config = f'''MXG = 0
MYG = 0
nout = {count}
timestep = {s['output_dt_s']:.17g}
[mesh]
nx = 1
ny = 1
nz = 1
[output]
enabled = false
[restart_files]
enabled = false
[all]
bndry_all = none
[solver]
type = rk4
atol = 1e-10
rtol = 1e-9
max_timestep = 0.001
[thermal]
'''
    config += ''.join(f'{k} = {v:.17g}\n' if isinstance(v, (float, np.floating))
                      else f'{k} = {v}\n' for k, v in options.items())
    (directory / 'BOUT.inp').write_text(config)
    # This is a single-process 0D run. UCX self transport avoids network requirements.
    env = dict(os.environ, UCX_TLS='self')
    with (directory / 'run.log').open('w') as log:
        subprocess.run([str(executable), '-d', str(directory.resolve())],
                       check=True, stdout=log, stderr=subprocess.STDOUT, env=env,
                       timeout=120)
    return np.loadtxt(directory / 'trajectory.csv', delimiter=',', skiprows=1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'results')
    parser.add_argument('--bout-executable', type=Path,
                        help='Optional compiled BOUT++ tomahawk_thermal executable')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    model = ThermalModel(ROOT / 'inputs')
    summaries = []
    baseline = None
    for name, overrides, initial_scale in scenarios(model.settings):
        case = ThermalModel(ROOT / 'inputs', overrides)
        initial = case.initial(initial_scale)
        times, states, status = case.solve(initial)
        rows = []
        for t, y in zip(times, states):
            rows.append(dict(time_s=float(t), Wthermal_MJ=float(y[0]),
                             Walpha_MJ=float(y[1]), Ein_MJ=float(y[2]),
                             Eout_MJ=float(y[3]), **case.powers(y)))
        with (out / (name + '.csv')).open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        residual = states[:, 0] + states[:, 1] - states[:, 2] + states[:, 3] - sum(initial[:2])
        summaries.append(dict(case=name, status=status, overrides=overrides,
                              initial_temperature_scale=initial_scale,
                              final_time_s=float(times[-1]),
                              initial_peak_T_keV=rows[0]['T_peak_keV'],
                              final_peak_T_keV=rows[-1]['T_peak_keV'],
                              max_energy_identity_residual_MJ=float(np.max(np.abs(residual)))))
        if name == 'reference':
            baseline = (times, states)
    table = np.loadtxt(ROOT / 'inputs/bosch_hale_uw_table6.csv', delimiter=',', skiprows=1)
    ref_error = float(np.max(np.abs(reactivity(table[:, 0]) * 1e6 / table[:, 1] - 1)))
    checks = dict(reactivity_reference_max_relative_error=ref_error,
                  reactivity_reference_tolerance=0.005,
                  reactivity_reference_pass=ref_error < 0.005,
                  energy_identity_pass=all(s['max_energy_identity_residual_MJ'] < 1e-6 for s in summaries),
                  native_comparison_performed=False,
                  python_version=sys.version.split()[0], numpy_version=np.__version__,
                  scipy_version=scipy.__version__)
    if args.bout_executable:
        executable = args.bout_executable.resolve(strict=True)
        full = native_run(executable, model, out / 'native_full', model.initial(), 5.0)
        first = native_run(executable, model, out / 'native_restart_first', model.initial(), 2.5)
        second = native_run(executable, model, out / 'native_restart_second', first[-1, 1:], 2.5,
                            offset=float(first[-1, 0]))
        native_error = float(np.max(np.abs(full[:, 1:] - baseline[1])))
        restart_error = float(np.max(np.abs(full[250:, 1:] - second[:, 1:])))
        checks.update(native_comparison_performed=True,
                      native_vs_radau_max_state_difference_MJ=native_error,
                      restart_max_state_difference_MJ=restart_error,
                      native_vs_radau_pass=native_error < 1e-5,
                      checkpoint_restart_pass=restart_error < 1e-5)
        if not np.allclose(full[:, 0], baseline[0], rtol=0, atol=1e-10):
            raise RuntimeError('Comparison time grids differ')
        if not np.allclose(full[250:, 0], second[:, 0], rtol=0, atol=1e-10):
            raise RuntimeError('Restart time grids differ')
    (out / 'summary.json').write_text(json.dumps(summaries, indent=2) + '\n')
    (out / 'numerical_checks.json').write_text(json.dumps(checks, indent=2) + '\n')
    print(json.dumps(checks, indent=2))
    if not all(v for k, v in checks.items() if k.endswith('_pass')):
        raise SystemExit('A numerical check failed; inspect numerical_checks.json')


if __name__ == '__main__':
    main()
