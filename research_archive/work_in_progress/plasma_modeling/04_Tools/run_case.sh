#!/bin/bash
# run_case.sh NAME GRID N [extra BOUT++ options...]
export PATH=/home/claude/opt/bin:$PATH LD_LIBRARY_PATH=/home/claude/opt/lib
P=/home/claude/plasma; NAME=$1; GRID=$2; N=$3; shift 3
D=$P/runs/$NAME; rm -rf $D; mkdir -p $D; cp $P/runs/template/BOUT.inp $D/; cp $P/grids/$GRID $D/
cd $D; T0=$(date +%s)
mpiexec -n 2 $P/elmpb/build/elm_pb -d . grid=$GRID zperiod=$N "$@" > run.log 2>&1; RC=$?
echo "$NAME rc=$RC wall=$(( $(date +%s) - T0 ))s"
python3 $P/tools/bout_results.py $D --grid $D/$GRID | tail -1
