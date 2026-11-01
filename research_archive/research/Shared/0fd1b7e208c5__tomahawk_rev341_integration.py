"""Rev3.4.1 integration corrections. No physics or facility execution is implied.

Standard-library-only preflight, energy accounting, transport input validation,
and PBS script generation. Historical input/output archives are read-only.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import tempfile
import unittest

REVISION = '3.4.1'
EV_J = 1.602176634e-19

def finite(value, label, positive=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError(f'{label}: finite number required')
    if positive and value <= 0: raise ValueError(f'{label}: positive number required')
    return float(value)

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def baseline():
    return {
      'revision':REVISION,
      'source_specification':'TOMAHAWK-SIS-COMPUTATIONAL-004 Rev3.4',
      'active_blanket':{'branch_id':'S20_AQUEOUS_EV010','density_kg_m3':1210.0,
        'li6_isotopic_fraction':0.90,'nuclear_library':'JENDL-5',
        'material_card':None,'transport_geometry':None,'transport_result':None},
      'requirements':{'tbr_min':1.15,'conductor_peak_T_max':35.0},
      'geometry':{'frame':'right_handed_xyz_m','R0_m':7.5,'a_bounding_m':3.0,
        'reference_volume_m3':950.0,'cad_to_equilibrium_map':None},
      'profiles':{'n_D0_m3':1.2e20,'n_T0_m3':1.2e20,'provenance':'prescribed_hot_profile_not_fill_gas'},
      'fill_state':{'pressure_Pa':0.300,'temperature_K':300.0,
        'number_density_gas_particles_m3':0.300/(1.380649e-23*300),
        'species_and_hot_state_conversion':None},
      'equilibrium':{'result':None,'cad_field_transform':None},
      'alpha_transport':{'result':None,'physical_horizon_s':0.25},
      'driver_transport':{'result':None,'module_energy_J':2.50e6,'repetition_Hz':10.0},
      'active_closures':{'neutron_capture_fraction':None,'alpha_deposition_fraction':None,
        'laser_absorption_fraction':None,'tbr_achieved':None},
      'legacy_only':{'blanket':'FLiBe','neutron_capture_fraction':0.95,
        'alpha_deposition_fraction':0.90,'laser_absorption_fraction':0.86,
        'tbr_assumption':1.15,'use_in_active_prediction':False},
      'gate_status':{**{f'G{i}':'UNRESOLVED' for i in range(1,5)},
        **{f'G{i}':'NOT_ASSESSABLE' for i in range(5,8)}},
      'allocation':{'machine':'Polaris','node_hours':5000,'basis':'SIS_REPORTED_NOT_JOB_LOG_VERIFIED',
        'partition':{'EV-011A':500,'EV-011B':900,'EV-011C':1500,'EV-012AB':700,'EV-012CD':1000,'review':400}},
      'schema_note':'Nulls are required data not supplied. No legacy value is substituted.'}

def validate_baseline(c):
    if c['revision'] != REVISION: raise ValueError('Wrong integration revision')
    b=c['active_blanket']
    if b['branch_id']!='S20_AQUEOUS_EV010': raise ValueError('Active blanket must be SIS S20, not historical FLiBe')
    if (b['density_kg_m3'],b['li6_isotopic_fraction'],b['nuclear_library'])!=(1210.0,0.90,'JENDL-5'):
        raise ValueError('S20 density, enrichment or library changed; issue a reviewed baseline revision')
    if c['legacy_only']['use_in_active_prediction'] is not False: raise ValueError('Historical closures cannot drive current predictions')
    if sum(c['allocation']['partition'].values()) != c['allocation']['node_hours']:
        raise ValueError('Node-hour partition does not close')
    for k,v in c['active_closures'].items():
        if v is not None: raise ValueError(f'{k}: active closures must be derived from registered result, not constants')
    return True

def heating_density(heating_eV_per_source, source_rate_s, volume_m3):
    h=finite(heating_eV_per_source,'heating'); s=finite(source_rate_s,'source rate',True)
    v=finite(volume_m3,'cell volume',True)
    if h<0: raise ValueError('Negative heating tally')
    return h*EV_J*s/v

def confinement(stored_energy_J, heating_W, dWdt_W):
    w=finite(stored_energy_J,'stored energy',True)
    loss=finite(heating_W,'heating')-finite(dWdt_W,'stored-energy derivative')
    if loss<=0: raise ValueError('Confinement time undefined for nonpositive inferred loss')
    return {'loss_W':loss,'tau_E_s':w/loss}

def cycle_power(mdot_kg_s, ht_in, ht_out, hc_in, hc_out, generator_efficiency, auxiliary_electric_W):
    m=finite(mdot_kg_s,'cycle flow',True)
    vals=[finite(x,'enthalpy') for x in [ht_in,ht_out,hc_in,hc_out]]
    eta=finite(generator_efficiency,'generator efficiency',True)
    if eta>1: raise ValueError('Generator efficiency exceeds one')
    aux=finite(auxiliary_electric_W,'auxiliary power')
    if aux<0: raise ValueError('Negative auxiliary power')
    turbine=m*(vals[0]-vals[1]); compressor=m*(vals[3]-vals[2])
    if turbine<0 or compressor<0: raise ValueError('Wrong turbine/compressor state ordering')
    shaft=turbine-compressor
    return {'turbine_W':turbine,'compressor_W':compressor,'cycle_shaft_W':shaft,'net_electric_W':eta*shaft-aux}

def validate_transport(result, config):
    validate_baseline(config)
    if result.get('branch_id')!=config['active_blanket']['branch_id']:
        raise ValueError('Transport and active blanket branch mismatch')
    if result.get('basis')!='COUPLED_NEUTRON_PHOTON_TRANSPORT':
        raise ValueError('First-collision, synthetic and bookkeeping records are not deposition transport')
    if result.get('nuclear_library')!='JENDL-5': raise ValueError('Library mismatch')
    if result.get('units')!={'heating':'eV/source','volume':'m3','source_rate':'1/s'}:
        raise ValueError('Explicit transport units missing or wrong')
    histories=result.get('histories')
    if isinstance(histories,bool) or not isinstance(histories,int) or histories<=0:
        raise ValueError('Positive integer history count required')
    for key in ['geometry_sha256','materials_sha256','nuclear_data_sha256','executable_sha256']:
        if not re.fullmatch(r'[0-9a-f]{64}',str(result.get(key,''))): raise ValueError(f'Missing {key}')
    rate=finite(result['source_rate_s'],'source rate',True)
    if not result.get('cells'): raise ValueError('No material-resolved heating cells')
    total=0.0; seen=set()
    for c in result['cells']:
        if c['cell_id'] in seen: raise ValueError('Duplicate cell id')
        seen.add(c['cell_id'])
        heating_density(c['heating_eV_per_source'],rate,c['volume_m3'])
        if finite(c['relative_standard_error'],'tally error')<0: raise ValueError('Negative tally error')
        total += c['heating_eV_per_source']*EV_J*rate
    tbr=finite(result['tritium_per_source'],'tritium tally')/finite(result['DT_burns_per_source'],'burn normalization',True)
    if tbr<0: raise ValueError('Negative TBR')
    return {'heating_W':total,'tbr_achieved':tbr,'tbr_meets_requirement':tbr>=config['requirements']['tbr_min'],
      'qualification':'SCHEMA_AND_ARITHMETIC_ONLY_NOT_PHYSICAL_VALIDATION'}

def registered_file(ref, base):
    if not isinstance(ref,dict) or not ref.get('path') or not ref.get('sha256'):
        raise ValueError('Required physical input has not been registered')
    path=Path(ref['path'])
    if not path.is_absolute(): path=base/path
    if not path.is_file(): raise ValueError(f'Required input missing: {path}')
    if digest(path)!=ref['sha256']: raise ValueError(f'Input hash mismatch: {path.name}')
    return path

def production_preflight(config, base):
    validate_baseline(config)
    required=[config['active_blanket'][k] for k in ['material_card','transport_geometry','transport_result']]
    required += [config['geometry']['cad_to_equilibrium_map'],config['equilibrium']['result'],
      config['equilibrium']['cad_field_transform'],config['alpha_transport']['result'],config['driver_transport']['result']]
    missing=sum(x is None for x in required)
    if missing: raise ValueError(f'{missing} required physical records absent; no integrated prediction generated')
    paths=[registered_file(x,base) for x in required]
    result=json.loads(paths[2].read_text())
    if result.get('materials_sha256')!=digest(paths[0]) or result.get('geometry_sha256')!=digest(paths[1]):
        raise ValueError('Transport result does not reference the registered material/geometry files')
    # Field/particle files are identity-checked here, not scientifically qualified.
    # Passing the schema never authorizes production or closes a physical gate.
    return validate_transport(result,config)

def pbs_text(executable, arguments=(), nodes=1, walltime='00:30:00', queue='debug'):
    # Project supplied explicitly to qsub -A; never invent a project/account.
    if isinstance(nodes,bool) or not isinstance(nodes,int) or nodes<1: raise ValueError('Invalid nodes')
    if not re.fullmatch(r'\d{1,3}:[0-5]\d:[0-5]\d',walltime): raise ValueError('Invalid walltime')
    if not re.fullmatch(r'[A-Za-z0-9_-]+',queue): raise ValueError('Invalid queue')
    command=' '.join(shlex.quote(str(a)) for a in [executable,*arguments])
    return '\n'.join(['#!/bin/bash -l','# Generated by Tomahawk Rev3.4.1; submit with qsub -A APPROVED_PROJECT this_file.pbs',
      '#PBS -N tomahawk-preflight',f'#PBS -l select={nodes}',f'#PBS -l walltime={walltime}',
      '#PBS -l filesystems=home:eagle',f'#PBS -q {queue}','#PBS -j oe','set -euo pipefail',
      'cd "${PBS_O_WORKDIR:?Submit from the staged package directory}"',
      '# Load the site-approved Python/solver environment before submission.',command,''])

class Tests(unittest.TestCase):
    def test_s20_active(self):
        self.assertTrue(validate_baseline(baseline()))
        c=baseline(); c['active_blanket']['density_kg_m3']=2000
        with self.assertRaises(ValueError): validate_baseline(c)
    def test_flibe_rejected(self):
        c=baseline(); c['active_blanket']['branch_id']='FLiBe'
        with self.assertRaises(ValueError): validate_baseline(c)
    def test_assumed_capture_rejected(self):
        c=baseline(); c['active_closures']['neutron_capture_fraction']=.95
        with self.assertRaises(ValueError): validate_baseline(c)
    def test_legacy_use_rejected(self):
        c=baseline(); c['legacy_only']['use_in_active_prediction']=True
        with self.assertRaises(ValueError): validate_baseline(c)
    def test_node_budget(self): self.assertEqual(sum(baseline()['allocation']['partition'].values()),5000)
    def test_confinement_no_double_derivative(self): self.assertEqual(confinement(20,12,2),{'loss_W':10.,'tau_E_s':2.})
    def test_nonpositive_loss(self):
        with self.assertRaises(ValueError): confinement(20,2,3)
    def test_eV_conversion(self): self.assertAlmostEqual(heating_density(1e6,1e12,2),.0801088317)
    def test_zero_volume(self):
        with self.assertRaises(ValueError): heating_density(1,1,0)
    def test_cycle_no_heat_rejection_double_count(self):
        r=cycle_power(2,1000,600,100,200,.9,20)
        self.assertEqual(r['cycle_shaft_W'],600); self.assertEqual(r['net_electric_W'],520)
    def test_first_collision_rejected(self):
        with self.assertRaises(ValueError): validate_transport({'branch_id':'S20_AQUEOUS_EV010','basis':'FIRST_COLLISION'},baseline())
    def test_transport_arithmetic_fixture_only(self):
        r={'branch_id':'S20_AQUEOUS_EV010','basis':'COUPLED_NEUTRON_PHOTON_TRANSPORT',
          'nuclear_library':'JENDL-5','units':{'heating':'eV/source','volume':'m3','source_rate':'1/s'},
          'histories':100,'source_rate_s':1e12,'tritium_per_source':.94,'DT_burns_per_source':1,
          'cells':[{'cell_id':1,'heating_eV_per_source':1e6,'volume_m3':2,'relative_standard_error':.1}],
          **{k:'0'*64 for k in ['geometry_sha256','materials_sha256','nuclear_data_sha256','executable_sha256']}}
        result=validate_transport(r,baseline())
        self.assertAlmostEqual(result['heating_W'],.1602176634)
        self.assertFalse(result['tbr_meets_requirement'])
        r['units']['heating']='MeV/source'
        with self.assertRaises(ValueError): validate_transport(r,baseline())
    def test_missing_physics_stops(self):
        with self.assertRaises(ValueError): production_preflight(baseline(),Path('.'))
    def test_pbs_not_slurm(self):
        s=pbs_text('python3',['tomahawk_rev341_integration.py','self-test']); self.assertIn('#PBS',s); self.assertNotIn('#SBATCH',s)
    def test_command_quoting(self): self.assertIn("'a b'",pbs_text('/path/a',['a b']))
    def test_queue_injection_rejected(self):
        with self.assertRaises(ValueError): pbs_text('python3',queue='debug\nmalicious')
    def test_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'record.json'; f.write_text('{}'); r={'path':f.name,'sha256':digest(f)}
            self.assertEqual(registered_file(r,Path(tmp)),f)
            f.write_text('{"changed":true}')
            with self.assertRaises(ValueError): registered_file(r,Path(tmp))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init','self-test','check','prepare-pbs'])
    parser.add_argument('--directory',type=Path,default=Path('.'))
    parser.add_argument('--config',type=Path)
    parser.add_argument('--production',action='store_true')
    parser.add_argument('--report',type=Path)
    a=parser.parse_args()
    if a.action=='init':
        a.directory.mkdir(parents=True,exist_ok=True)
        target=a.directory/'active_baseline_rev341.json'
        if target.exists(): raise SystemExit('Refusing to overwrite an existing active configuration')
        target.write_text(json.dumps(baseline(),indent=2)+'\n'); print(target)
    elif a.action=='self-test':
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        report={'revision':REVISION,'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
          'status':'PASS' if result.wasSuccessful() else 'FAIL','scope':'SOFTWARE_AND_ARITHMETIC_ONLY',
          'physics_run_performed':False,'facility_job_submitted':False}
        if a.report: a.report.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report)); raise SystemExit(0 if result.wasSuccessful() else 1)
    elif a.action=='check':
        if a.config is None: parser.error('--config required')
        c=json.loads(a.config.read_text()); validate_baseline(c)
        print(json.dumps(production_preflight(c,a.config.parent) if a.production else {'configuration':'PASS','production_ready':False}))
    elif a.action=='prepare-pbs':
        target=a.directory/'polaris_verify.pbs'
        if target.exists(): raise SystemExit('Refusing to overwrite an existing job script')
        target.write_text(pbs_text('python3',['tomahawk_rev341_integration.py','self-test','--report','polaris_verification_report.json']))
        print(target)

if __name__=='__main__': main()
