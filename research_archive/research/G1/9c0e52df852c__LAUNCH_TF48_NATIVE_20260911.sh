#!/usr/bin/env bash
# Tomahawk TF48 native MAKEGRID launcher.
#
# This launcher is deliberately fail-closed:
#   * no Docker job starts without the verified TF48 input set;
#   * the native output is validated before it is marked usable;
#   * the TF edge-ripple gate is strict: edge ripple must be < 1.0 percent;
#   * no VMEC, DESC, or other equilibrium solver is launched here.

set -u

readonly LAUNCHER_VERSION="TOMAHAWK-TF48-NATIVE-LAUNCHER-1.0"
readonly DOWNLOADS_DIR="/home/nicole/Downloads"
readonly WINDOWS_DOWNLOADS_DIR="/mnt/c/Users/Nicol/Downloads"
readonly WINDOWS_EXPORT_DIR="/mnt/c/Users/Nicol/OneDrive"
readonly DOCKER_IMAGE="stellopt-full"
readonly XGRID_IN_CONTAINER="/home/STELLOPT/MAKEGRID/Release/xgrid"
readonly TF_RIPPLE_LIMIT_PERCENT="1.0"
readonly TF_REFERENCE_RIPPLE_PERCENT="0.7539158737"
readonly TF_BRANCH="CAD_A2_TF48_INTERLEAVED_SCREENING_CORRECTION"

pause_on_block() {
  local message="$1"
  echo "TF48_LAUNCH_BLOCKED: ${message}" >&2
  if [[ -t 0 ]]; then
    read -r -p "Press Enter to leave this Ubuntu window open... " _ || true
  fi
  exit 2
}

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
package_spec="${1:-}"

# If this launcher is inside an extracted run kit, use that directory directly.
if [[ -z "${package_spec}" && -f "${script_dir}/TF48_INPUT_MANIFEST.json" ]]; then
  package_spec="${script_dir}"
fi

# Otherwise locate only the corrected package name. Older handoffs are not accepted.
if [[ -z "${package_spec}" ]]; then
  for search_dir in "${DOWNLOADS_DIR}" "${WINDOWS_DOWNLOADS_DIR}"; do
    [[ -d "${search_dir}" ]] || continue
    package_spec="$(find "${search_dir}" -maxdepth 1 -type f \
      -iname 'Tomahawk_TF48_MGRID_FIX_HANDOFF*.zip' -print -quit 2>/dev/null || true)"
    [[ -n "${package_spec}" ]] && break
  done
fi

[[ -n "${package_spec}" ]] || pause_on_block \
  "the corrected TF48 package is not in ${DOWNLOADS_DIR} or ${WINDOWS_DOWNLOADS_DIR}."
[[ -e "${package_spec}" ]] || pause_on_block \
  "package path does not exist: ${package_spec}"

command -v python3 >/dev/null 2>&1 || pause_on_block "python3 is not installed."
command -v docker >/dev/null 2>&1 || pause_on_block "docker is not available in this Ubuntu shell."
docker image inspect "${DOCKER_IMAGE}" >/dev/null 2>&1 || pause_on_block \
  "Docker image ${DOCKER_IMAGE} is not available locally."
[[ -d "${WINDOWS_EXPORT_DIR}" ]] || pause_on_block \
  "OneDrive export directory is not available: ${WINDOWS_EXPORT_DIR}"

# Create a fresh user-writable staging directory. It is placed in Downloads when
# possible so the generated output ZIP is easy to retrieve.
run_dir="$(mktemp -d "${DOWNLOADS_DIR}/Tomahawk_TF48_NATIVE_RUN.XXXXXX" 2>/dev/null || true)"
if [[ -z "${run_dir}" ]]; then
  run_dir="$(mktemp -d "/home/nicole/Tomahawk_TF48_NATIVE_RUN.XXXXXX" 2>/dev/null || true)"
fi
if [[ -z "${run_dir}" ]]; then
  run_dir="$(mktemp -d "/tmp/Tomahawk_TF48_NATIVE_RUN.XXXXXX" 2>/dev/null || true)"
fi
[[ -n "${run_dir}" ]] || pause_on_block "could not create a writable staging directory."

if [[ -f "${package_spec}" ]]; then
  python3 - "${package_spec}" "${run_dir}" <<'PY'
import os
import sys
import zipfile
from pathlib import Path

archive = Path(sys.argv[1])
destination = Path(sys.argv[2]).resolve()
required = {
    "TF48_INPUT_MANIFEST.json",
    "coils.tomahawk_tf48",
    "extcur.tomahawk_tf48",
    "input_xgrid_tomahawk_tf48",
    "validate_tf48_mgrid.py",
    "RUN_TF48_NATIVE_FIXED.sh",
}

with zipfile.ZipFile(archive) as handle:
    if handle.testzip() is not None:
        raise RuntimeError("ZIP CRC check failed")
    names = [name for name in handle.namelist() if not name.endswith("/")]
    missing = sorted(
        name for name in required
        if not any(item == name or item.endswith("/" + name) for item in names)
    )
    if missing:
        raise RuntimeError("ZIP is not the corrected TF48 package; missing " + ", ".join(missing))
    for name in names:
        target = (destination / name).resolve()
        if target != destination and destination not in target.parents:
            raise RuntimeError("unsafe ZIP member path: " + name)
    handle.extractall(destination)
PY
  extract_rc=$?
  [[ "${extract_rc}" -eq 0 ]] || pause_on_block "ZIP validation/extraction failed."
else
  [[ -d "${package_spec}" ]] || pause_on_block "package is neither a ZIP nor a directory."
  cp -a "${package_spec}/." "${run_dir}/" || pause_on_block "could not copy the package."
fi

# Require the exact native files before Docker is launched.
for required_file in \
  TF48_INPUT_MANIFEST.json \
  coils.tomahawk_tf48 \
  extcur.tomahawk_tf48 \
  input_xgrid_tomahawk_tf48 \
  validate_tf48_mgrid.py \
  RUN_TF48_NATIVE_FIXED.sh \
  SETUP_TF48_NATIVE_ENV.sh; do
  [[ -f "${run_dir}/${required_file}" ]] || pause_on_block \
    "extracted package is missing ${required_file}."
done

# Reject a stale or alternate TF branch before Docker is launched. This guard
# is independent of the later native-MGRID ripple calculation.
python3 - "${run_dir}/TF48_INPUT_MANIFEST.json" "${run_dir}/TF48_SOURCE_GUARD.json" <<'PY'
import json
import math
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
geometry = manifest.get("geometry", {})
checks = {
    "branch": manifest.get("branch") == "CAD_A2_TF48_INTERLEAVED_SCREENING_CORRECTION",
    "physical_coils": geometry.get("physical_coils") == 48,
    "turns_per_physical_coil": geometry.get("turns_per_physical_coil") == 100,
    "segments_per_coil": geometry.get("segments_per_coil") == 512,
    "field_periods": geometry.get("field_periods") == 16,
    "ripple_limit_percent": geometry.get("edge_ripple_limit_percent") == 1.0,
    "reference_below_limit": float(geometry.get("edge_ripple_reference_percent", float("nan"))) < 1.0,
    "reference_value": math.isclose(
        float(geometry.get("edge_ripple_reference_percent", float("nan"))),
        0.7539158737,
        rel_tol=0.0,
        abs_tol=1e-10,
    ),
}
guard = {
    "schema_version": "TOMAHAWK-TF48-SOURCE-GUARD-1.0",
    "branch": manifest.get("branch"),
    "expected_branch": "CAD_A2_TF48_INTERLEAVED_SCREENING_CORRECTION",
    "physical_coils": geometry.get("physical_coils"),
    "field_periods": geometry.get("field_periods"),
    "edge_ripple_limit_percent": 1.0,
    "comparison": "edge_ripple_percent < 1.0",
    "reference_edge_ripple_percent": geometry.get("edge_ripple_reference_percent"),
    "checks": checks,
    "pass": all(checks.values()),
}
out_path.write_text(json.dumps(guard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if not guard["pass"]:
    print(json.dumps(guard, indent=2, sort_keys=True))
    raise SystemExit(2)
print("TF48_SOURCE_GUARD_PASS")
print("TF48_PHYSICAL_COILS=48")
print("TF48_FIELD_PERIODS=16")
print("TF_EDGE_RIPPLE_LIMIT_PERCENT=1.0")
print("TF_EDGE_RIPPLE_COMPARISON=edge_ripple_percent<1.0")
PY
guard_rc=$?
[[ "${guard_rc}" -eq 0 ]] || pause_on_block "TF48 source branch or 1% ripple guard failed."

run_metadata="${run_dir}/TF48_HOST_RUN_METADATA.txt"
cat > "${run_metadata}" <<EOF
launcher_version=${LAUNCHER_VERSION}
windows_downloads_dir=${WINDOWS_DOWNLOADS_DIR}
tf_branch=${TF_BRANCH}
tf_physical_coils=48
tf_field_periods=16
tf_edge_ripple_limit_percent=${TF_RIPPLE_LIMIT_PERCENT}
tf_edge_ripple_comparison=STRICTLY_LESS_THAN
tf_reference_ripple_percent=${TF_REFERENCE_RIPPLE_PERCENT}
docker_image=${DOCKER_IMAGE}
xgrid_in_container=${XGRID_IN_CONTAINER}
windows_export_dir=${WINDOWS_EXPORT_DIR}
package_source=${package_spec}
EOF

container_name="tomahawk_tf48_native_$(date +%Y%m%d_%H%M%S)_$$"

# The container is detached so closing Ubuntu does not interrupt MAKEGRID.
# The postprocessor always creates an output ZIP, including rejected runs.
container_id="$(docker run -d \
  --platform linux/amd64 \
  --name "${container_name}" \
  -e "TF_RIPPLE_LIMIT_PERCENT=${TF_RIPPLE_LIMIT_PERCENT}" \
  -e "TF_REFERENCE_RIPPLE_PERCENT=${TF_REFERENCE_RIPPLE_PERCENT}" \
  -e "TF_BRANCH=${TF_BRANCH}" \
  -e "TF_WINDOWS_EXPORT_DIR=/export" \
  -v "${run_dir}:/data" \
  -v "${WINDOWS_EXPORT_DIR}:/export" \
  "${DOCKER_IMAGE}" \
  bash -lc '
    cd /data || exit 11
    mkdir -p /data/native_output
    bash ./SETUP_TF48_NATIVE_ENV.sh > /data/native_output/environment_setup.log 2>&1
    env_rc=$?
    if [ "$env_rc" -ne 0 ]; then
      rc="$env_rc"
    else
      STELLOPT_XGRID=/home/STELLOPT/MAKEGRID/Release/xgrid \
        bash ./RUN_TF48_NATIVE_FIXED.sh
      rc=$?
    fi

    python3 - "$rc" <<'"'"'PY'"'"'
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

base = Path("/data")
output = base / "native_output"
output.mkdir(parents=True, exist_ok=True)
try:
    wrapper_rc = int(sys.argv[1])
except (IndexError, ValueError):
    wrapper_rc = 99

limit = float(os.environ.get("TF_RIPPLE_LIMIT_PERCENT", "1.0"))
validation_path = output / "tf48_native_validation.json"
edge_value = None
edge_pass = False
validation_status = "MISSING_VALIDATION_REPORT"
if validation_path.is_file():
    try:
        report = json.loads(validation_path.read_text(encoding="utf-8"))
        edge = report.get("mgrid_result", {}).get("checks", {}).get("edge_sample", {})
        edge_value = edge.get("edge_ripple_percent")
        validation_status = report.get("status", "UNKNOWN")
    except Exception as exc:
        validation_status = f"REPORT_READ_ERROR:{type(exc).__name__}:{exc}"

if isinstance(edge_value, (int, float)):
    edge_pass = float(edge_value) < limit

hard_gate = {
    "schema_version": "TOMAHAWK-TF48-STRICT-RIPPLE-GATE-1.0",
    "gate": "tf_edge_ripple",
    "comparison": "edge_ripple_percent < limit_percent",
    "limit_percent": limit,
    "edge_ripple_percent": edge_value,
    "strict_pass": edge_pass,
    "wrapper_exit_code": wrapper_rc,
    "validator_status": validation_status,
    "accepted_for_downstream_solver": bool(wrapper_rc == 0 and edge_pass),
}
(output / "TF_EDGE_RIPPLE_HARD_GATE.json").write_text(
    json.dumps(hard_gate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
if wrapper_rc == 0 and not edge_pass:
    wrapper_rc = 5
if wrapper_rc == 0 and edge_pass:
    (output / "NATIVE_MGRID_ACCEPTED_TF_RIPPLE_BELOW_1_PERCENT.txt").write_text(
        "TF edge ripple passed the strict < 1.0% gate.\n", encoding="utf-8"
    )
else:
    (output / "NATIVE_MGRID_REJECTED_TF_RIPPLE_GATE.txt").write_text(
        "Do not use this MGRID downstream. TF edge ripple did not pass the strict < 1.0% gate.\n",
        encoding="utf-8",
    )

archive = base / "Tomahawk_TF48_NATIVE_OUTPUT_20260911.zip"
with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
    for path in sorted(output.rglob("*")):
        if path.is_file():
            handle.write(path, path.relative_to(base))
    metadata = base / "TF48_HOST_RUN_METADATA.txt"
    if metadata.is_file():
        handle.write(metadata, metadata.relative_to(base))
    handle.writestr("RUN_EXIT_CODE.txt", str(wrapper_rc) + "\n")
print(f"TF48_OUTPUT_ZIP={archive}")
print(f"TF_EDGE_RIPPLE_STRICT_PASS={edge_pass}")
export_dir = Path(os.environ.get("TF_WINDOWS_EXPORT_DIR", ""))
if export_dir.is_dir():
    exported = export_dir / archive.name
    try:
        shutil.copy2(archive, exported)
        print(f"TF48_OUTPUT_EXPORTED={exported}")
    except Exception as exc:
        print(f"TF48_OUTPUT_EXPORT_FAILED={type(exc).__name__}:{exc}")
else:
    print("TF48_OUTPUT_EXPORT_FAILED=export mount is unavailable")
sys.exit(wrapper_rc)
PY
    exit "$rc"
  ')"
docker_rc=$?

[[ "${docker_rc}" -eq 0 ]] || pause_on_block "Docker could not start the native run."

printf '%s\n' "${container_id}" > "${run_dir}/container_id"
echo "TF48_NATIVE_CONTAINER=${container_id}"
echo "TF48_RUN_DIRECTORY=${run_dir}"
echo "TF48_OUTPUT_ZIP=${run_dir}/Tomahawk_TF48_NATIVE_OUTPUT_20260911.zip"
echo "TF48_WINDOWS_EXPORT=/mnt/c/Users/Nicol/OneDrive/Tomahawk_TF48_NATIVE_OUTPUT_20260911.zip"
echo "CHECK_LIVE_LOGS: docker logs ${container_id}"
echo "CHECK_GATE: ${run_dir}/native_output/TF_EDGE_RIPPLE_HARD_GATE.json"
echo "The container is detached; closing Ubuntu will not stop it."
