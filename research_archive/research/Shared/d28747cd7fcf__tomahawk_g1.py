"""Tomahawk G1 boundary preparation and FreeCAD audit -- plain Python, no macro.

Ordinary Python (standard library only):
    python tomahawk_g1.py path/to/ev007_study_boundary_solid.step
FreeCAD Python console (runs CAD/mesh checks as well):
    import runpy
    runpy.run_path(r'C:/path/tomahawk_g1.py', run_name='__main__',
                   init_globals={'INPUT_STEP': r'C:/path/ev007_study_boundary_solid.step'})

Corrects ONLY the verified uploaded file's metre-numbers/mm-declaration mismatch.
No geometry fitting, smoothing, hole filling, or invented engineering geometry.
All numerical acceptance windows below are PROPOSED screening tolerances, not
approved SIS requirements. A script cannot sign an interface-control document.
"""
import argparse
import gzip
import html
import hashlib
import inspect
import json
import math
import os
import platform
import re
import shutil
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

VERSION = '1.2.0'
KNOWN_SHA256 = '871c8dc94ccff5b390cbd6d07a30eb2367e238edbefa8b66a042fecfb4a35764'
CORRECTED_SHA256 = '8317664cb1d897872fa73a4a73255ce7b5a4e32e2f18921a3d09f4dc066d2899'
INPUT_NAME = 'ev007_study_boundary_solid.step'
BACKUP_NAME = 'ev007_study_boundary.20260830-203304.FCBak'
PROPOSED = {
    'reference_volume_m3': 950.0,
    'reference_volume_relative_error_max': 0.01,
    'mesh_volume_relative_error_max': 0.002,
    'last_two_mesh_volume_relative_change_max': 0.001,
    'last_two_mesh_area_relative_change_max': 0.002,
    'step_roundtrip_relative_volume_error_max': 1e-6,
    'step_roundtrip_bbox_error_m_max': 1e-5,
    'mesh_deflections_mm': [20.0, 10.0, 5.0],
    'mesh_angular_deflection_rad': 0.15,
    'rotation_sample_distance_m_max': 0.001,
    'rotation_sample_count': 128,
    'boundary_periods_claimed': 16,
}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def corrected_bytes(raw):
    """Identity-bound unit correction; never guesses scale for an unknown design."""
    digest=hashlib.sha256(raw).hexdigest()
    if digest == CORRECTED_SHA256:
        return raw  # Already corrected: do not scale twice.
    if digest != KNOWN_SHA256:
        raise ValueError('Input differs from the reviewed upload. No automatic rescaling. '
                         'Select the reviewed original OR ev007_boundary_units_corrected.step.')
    old = b'SI_UNIT(.MILLI.,.METRE.)'
    if raw.count(old) != 1:
        raise ValueError('Expected exactly one millimetre length-unit declaration.')
    return raw.replace(old, b'SI_UNIT($,.METRE.)')


def windows_desktop():
    """Read the current user's actual Windows Desktop (including redirection)."""
    import ctypes
    import uuid
    from ctypes import wintypes
    guid=(ctypes.c_ubyte*16).from_buffer_copy(
        uuid.UUID('B4BFCC3A-DB2C-424C-B029-7FE99A87C641').bytes_le)
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    ole=ctypes.WinDLL('ole32',use_last_error=True)
    get_path=shell.SHGetKnownFolderPath
    get_path.argtypes=[ctypes.c_void_p,wintypes.DWORD,wintypes.HANDLE,ctypes.POINTER(ctypes.c_void_p)]
    get_path.restype=ctypes.c_long
    ole.CoTaskMemFree.argtypes=[ctypes.c_void_p]; ole.CoTaskMemFree.restype=None
    pointer=ctypes.c_void_p()
    try:
        result=get_path(ctypes.byref(guid),0,None,ctypes.byref(pointer))
        if result != 0 or not pointer.value:
            raise OSError('Windows could not locate your Desktop (HRESULT %s).' % result)
        return Path(ctypes.wstring_at(pointer.value))
    finally:
        if pointer.value: ole.CoTaskMemFree(pointer)


def desktop_directory():
    if sys.platform == 'win32':
        # Do not guess USERPROFILE/Desktop: OneDrive/localization may redirect it.
        return windows_desktop()
    try:
        from PySide import QtCore
        location=QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DesktopLocation)
        if location: return Path(location)
    except ImportError:
        pass
    candidate=Path.home()/'Desktop'
    if candidate.is_dir(): return candidate
    raise RuntimeError('Desktop could not be located. Set OUTPUT_PARENT or --output-parent explicitly.')


def save_readable_results(out, report):
    audit=report['cad_audit']; details=audit.get('details',{})
    rows=''.join('<tr><td>%s</td><td>%s</td><td><pre>%s</pre></td></tr>' %
                 (html.escape(name),html.escape(item['status']),
                  html.escape(json.dumps(item.get('value'),indent=2)))
                 for name,item in audit.get('checks',{}).items())
    preview='<img src="boundary_preview.png" alt="FreeCAD boundary view">' if (out/'boundary_preview.png').is_file() else ''
    progress=html.escape(json.dumps(details.get('checkpoint_events',[]),indent=2))
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Tomahawk G1 results</title>
    <style>body{font:16px system-ui;max-width:1080px;margin:35px auto;padding:20px;color:#173449}
    table{border-collapse:collapse;width:100%%}td,th{border:1px solid #ccd7df;padding:10px;text-align:left}
    pre{white-space:pre-wrap;overflow-wrap:anywhere}img{max-width:100%%}h1,h2{color:#104d62}</style>
    <h1>Tomahawk G1 results</h1><p>Saved to: %s</p><p><strong>CAD audit: %s</strong></p>
    <p>Formal G1: %s</p><p>CAD volume: %s m³</p>%s
    <h2>Numerical checks</h2><table><tr><th>Check</th><th>Result</th><th>Value</th></tr>%s</table>
    <h2>Progress this run</h2><pre>%s</pre>
    <h2>Messages</h2><pre>%s</pre>
    <p>Proposed screening tolerances only. No confinement, stability or engineering approval is implied.</p>
    <p>Send <strong>Tomahawk_G1_Evidence.zip</strong> for review. Full values are in g1_report.json.</p></html>''' % (
        html.escape(str(out)),html.escape(audit['status']),html.escape(report['g1_gate_status']),
        html.escape(str(details.get('cad_volume_m3','NOT COMPUTED'))),preview,rows,progress,
        html.escape(audit.get('message',audit.get('traceback',audit.get('note','')))))
    (out/'RESULTS.html').write_text(page,encoding='utf-8')


def show_output_folder(out):
    try:
        if sys.platform=='win32':
            os.startfile(str(out))
        else:
            from PySide import QtCore,QtGui
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(out)))
    except Exception as exc:
        print('Results are saved; open this folder manually: %s (%s)' % (out,exc))


class CheckpointCache:
    """Hash-verified, atomic checkpoints. Loading JSON never executes code."""
    def __init__(self, parent, output, contract):
        self.contract=contract
        self.key=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
        self.root=Path(parent)/'Checkpoints'/self.key
        self.root.mkdir(parents=True,exist_ok=True)
        self.output=Path(output); self.events=[]

    def record(self,event):
        self.events.append(event)
        write_json(self.output/'progress.json',{'checkpoint_key':self.key,'stages':self.events})

    def get(self,name):
        pointer=self.root/(name+'.json')
        if not pointer.is_file(): return None
        try:
            index=json.loads(pointer.read_text())
            directory=index['directory']
            if Path(directory).name!=directory or not directory.startswith(name+'_'):
                raise ValueError('Invalid checkpoint directory.')
            location=self.root/directory
            payload=(location/'payload.json.gz').read_bytes()
            if index['key']!=self.key or hashlib.sha256(payload).hexdigest()!=index['payload_sha256']:
                raise ValueError('Checkpoint payload changed.')
            for filename,digest in index['artifacts'].items():
                if Path(filename).name!=filename or sha(location/filename)!=digest:
                    raise ValueError('Checkpoint artifact changed: '+filename)
            data=json.loads(gzip.decompress(payload).decode('utf-8'))
            for filename in index['artifacts']:
                shutil.copy2(location/filename,self.output/filename)
            self.record({'stage':name,'action':'REUSED_VERIFIED_CHECKPOINT'})
            print('[G1] REUSED: '+name)
            return data
        except (OSError,ValueError,KeyError,TypeError,EOFError) as exc:
            self.record({'stage':name,'action':'INVALID_CHECKPOINT_RECOMPUTE','reason':str(exc)})
            print('[G1] Checkpoint invalid; recomputing '+name)
            return None

    def put(self,name,data,artifacts=()):
        location=Path(tempfile.mkdtemp(prefix=name+'_',dir=str(self.root)))
        payload=gzip.compress(json.dumps(data,allow_nan=False).encode('utf-8'),compresslevel=3)
        (location/'payload.json.gz').write_bytes(payload)
        hashes={}
        for filename in artifacts:
            if Path(filename).name!=filename: raise ValueError('Invalid artifact name.')
            shutil.copy2(self.output/filename,location/filename)
            hashes[filename]=sha(location/filename)
        index={'key':self.key,'contract':self.contract,'directory':location.name,
               'payload_sha256':hashlib.sha256(payload).hexdigest(),'artifacts':hashes}
        temp=self.root/(location.name+'.pending')
        write_json(temp,index)
        # Commit last. An interrupted write never presents a partial checkpoint.
        os.replace(str(temp),str(self.root/(name+'.json')))
        self.record({'stage':name,'action':'COMPUTED_AND_CHECKPOINTED'})


def audit_contract(corrected,App,Part):
    functions=[native_audit,mesh_statistics,bbox,export_vtk,sub,cross,dot]
    source='\n'.join(inspect.getsource(f) for f in functions)
    return {'geometry_sha256':sha(corrected),'settings':PROPOSED,
            'freecad_version':list(App.Version()),'occ_version':str(getattr(Part,'OCC_VERSION','unspecified')),
            'python_version':platform.python_version(),'platform':platform.platform(),
            'audit_code_sha256':hashlib.sha256(source.encode()).hexdigest()}


def backup_metadata(path):
    """Inspect XML only. Do not load or execute document objects."""
    if not path.is_file():
        return {'status': 'NOT_SUPPLIED_OPTIONAL'}
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read('Document.xml'))
    return {'status': 'XML_INSPECTED_ONLY', 'file': path.name, 'sha256': sha(path),
            'freecad_version': root.get('ProgramVersion'),
            'objects': [dict(x.attrib) for x in root.findall('./Objects/Object')],
            'labels': [s.get('value') for s in root.findall(".//Property[@name='Label']/String")],
            'note': 'Backup geometry was not compared with STEP. Original preserved.'}


def sub(a, b):
    return tuple(x-y for x,y in zip(a,b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def dot(a, b):
    return sum(x*y for x,y in zip(a,b))


def mesh_statistics(points, triangles):
    """Exact-coordinate seam identification; never weld gaps or remove facets.

    Coordinates are metres. Adjacent directed edges must cancel. Euler's
    formula is applied only to this triangulation, not BREP seam-edge counts.
    Vertex-link cycles also reject pinched/non-manifold vertices.
    """
    ids = {}; vertices = []; remap = []
    for p in points:
        p = tuple(float(x) for x in p)
        if len(p) != 3 or not all(math.isfinite(x) for x in p):
            raise ValueError('Nonfinite/invalid mesh point.')
        if p not in ids:
            ids[p] = len(vertices); vertices.append(p)
        remap.append(ids[p])
    faces = [tuple(remap[i] for i in t) for t in triangles]
    edges = {}; links = defaultdict(list); adjacency = defaultdict(set)
    degenerate = 0; seen = set(); duplicates = 0; volume = 0.; area = 0.
    for t in faces:
        if len(t) != 3:
            raise ValueError('Non-triangular facet.')
        key = tuple(sorted(t))
        duplicates += key in seen; seen.add(key)
        a,b,c = (vertices[i] for i in t)
        n = cross(sub(b,a),sub(c,a))
        ar = math.sqrt(dot(n,n))/2
        degenerate += len(set(t)) != 3 or ar <= 1e-20
        area += ar; volume += dot(a,cross(b,c))/6
        for u,v in [(t[0],t[1]),(t[1],t[2]),(t[2],t[0])]:
            k = tuple(sorted((u,v)))
            count, sign = edges.get(k,(0,0))
            edges[k] = (count+1,sign+(1 if u<v else -1))
            adjacency[u].add(v); adjacency[v].add(u)
        for v,a,b in [(t[0],t[1],t[2]),(t[1],t[2],t[0]),(t[2],t[0],t[1])]:
            links[v].append((a,b))
    def components(graph):
        remaining=set(graph); count=0
        while remaining:
            stack=[remaining.pop()]; count+=1
            while stack:
                for j in graph[stack.pop()]:
                    if j in remaining:
                        remaining.remove(j); stack.append(j)
        return count
    bad_links=0
    for pairs in links.values():
        graph=defaultdict(set); degree=defaultdict(int)
        for a,b in pairs:
            graph[a].add(b); graph[b].add(a); degree[a]+=1; degree[b]+=1
        bad_links += any(n!=2 for n in degree.values()) or components(graph)!=1
    boundary=sum(n==1 for n,_ in edges.values())
    nonmanifold=sum(n!=2 for n,_ in edges.values())
    orientation=sum(n==2 and s!=0 for n,s in edges.values())
    comp=components(adjacency)
    chi=len(adjacency)-len(edges)+len(faces)
    closed=bool(faces) and not (degenerate or duplicates or nonmanifold or bad_links)
    stats={'vertices':len(vertices),'triangles':len(faces),'edges':len(edges),
           'exact_duplicate_vertices_identified':len(points)-len(vertices),
           'boundary_edges':boundary,'nonmanifold_edges':nonmanifold,
           'nonmanifold_vertices':bad_links,'inconsistent_edge_orientations':orientation,
           'degenerate_triangles':degenerate,'duplicate_triangles':duplicates,
           'connected_components':comp,'euler_characteristic':chi,
           'genus':(2-chi)/2 if closed and comp==1 and not orientation else None,
           'watertight_manifold':closed,'signed_volume_m3':volume,'area_m2':area,
           'note':'Topology alone does not test triangle self-intersections.'}
    return stats, vertices, faces


def export_vtk(path, points, faces):
    with path.open('w',encoding='ascii') as f:
        f.write('# vtk DataFile Version 3.0\nTomahawk boundary; coordinates in metres\nASCII\nDATASET POLYDATA\n')
        f.write('POINTS %d double\n' % len(points))
        for p in points: f.write('%.16g %.16g %.16g\n' % tuple(p))
        f.write('POLYGONS %d %d\n' % (len(faces),4*len(faces)))
        for t in faces: f.write('3 %d %d %d\n' % tuple(t))


def bbox(shape):
    b=shape.BoundBox
    return [v/1000 for v in [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]]


def native_audit(corrected, out):
    import FreeCAD as App
    import Part
    import MeshPart
    started=time.monotonic(); checks={}; details={}
    cache=CheckpointCache(out.parent,out,audit_contract(corrected,App,Part))
    complete=cache.get('complete_audit')
    if complete is not None:
        complete['details']['this_run_elapsed_seconds']=time.monotonic()-started
        complete['details']['checkpoint_events']=cache.events
        complete['details']['all_native_checks_reused']=True
        return complete
    def check(name, condition, value=None):
        checks[name]={'status':'PASS' if condition else 'FAIL','value':value}
    def log(message):
        print('[G1] '+message)
    log('Importing corrected metre-unit STEP; FreeCAD stores lengths internally in mm.')
    shape=Part.read(str(corrected))
    details['freecad_version']=list(App.Version())
    details['checkpoint_key']=cache.key
    details['brep_counts']={k:len(getattr(shape,k)) for k in ['Solids','Shells','Faces','Edges','Vertexes']}
    brep=cache.get('brep_checks')
    if brep is not None:
        checks.update(brep)
    else:
        check('brep_valid',not shape.isNull() and shape.isValid())
        check('one_closed_solid',len(shape.Solids)==1 and len(shape.Shells)==1 and
              shape.isClosed() and len(shape.Faces)==len(shape.Solids[0].Faces))
        try:
            shape.check(True)  # None on success; raises on diagnostic failure.
            check('brep_bop_check',True)
        except Exception as exc:
            check('brep_bop_check',False,str(exc))
        cache.put('brep_checks',dict(checks))
    if not all(v['status']=='PASS' for v in checks.values()):
        details['checkpoint_events']=list(cache.events)
        result={'status':'FAIL','checks':checks,'details':details,
                'note':'Mesh/export promotion stopped on BREP failure; corrected STEP retained.'}
        cache.put('complete_audit',result)
        return result
    volume=abs(shape.Volume)/1e9
    details.update(cad_volume_m3=volume,cad_area_m2=shape.Area/1e6,bbox_m=bbox(shape))
    verr=abs(volume/PROPOSED['reference_volume_m3']-1)
    check('volume_reconciliation_proposed',verr<=PROPOSED['reference_volume_relative_error_max'],verr)
    doc=App.newDocument('TomahawkG1Boundary')
    obj=doc.addObject('Part::Feature','EV007_CandidateBoundary')
    obj.Label='EV007 candidate boundary - unit corrected - G1 review pending'
    obj.Shape=shape
    obj.addProperty('App::PropertyString','SourceSHA256','Provenance'); obj.SourceSHA256=sha(corrected)
    obj.addProperty('App::PropertyString','G1Status','Provenance'); obj.G1Status='UNRESOLVED_PENDING_REVIEW'
    doc.recompute()
    export_names=['ev007_candidate_boundary.FCStd','ev007_candidate_boundary_mm.brep','ev007_roundtrip.step']
    exported=cache.get('cad_exports_roundtrip')
    if exported is not None:
        checks['step_roundtrip']=exported
    else:
        doc.saveAs(str(out/export_names[0]))
        shape.exportBrep(str(out/export_names[1]))
        shape.exportStep(str(out/export_names[2]))
        roundtrip=Part.read(str(out/export_names[2]))
        rv=abs(abs(roundtrip.Volume)/1e9-volume)/max(volume,1e-30)
        rb=max(abs(a-b) for a,b in zip(bbox(shape),bbox(roundtrip)))
        check('step_roundtrip',roundtrip.isValid() and len(roundtrip.Solids)==1 and
              rv<=PROPOSED['step_roundtrip_relative_volume_error_max'] and
              rb<=PROPOSED['step_roundtrip_bbox_error_m_max'],{'relative_volume_error':rv,'bbox_error_m':rb})
        cache.put('cad_exports_roundtrip',checks['step_roundtrip'],export_names)
    records=[]; finest=None; raw_mesh=None
    for deflection in PROPOSED['mesh_deflections_mm']:
        stage='mesh_'+str(deflection).replace('.','_')
        cached_mesh=cache.get(stage)
        if cached_mesh is not None:
            records.append(cached_mesh['stats'])
            if 'vertices' in cached_mesh:
                finest=(cached_mesh['vertices'],cached_mesh['faces'])
                checks['finest_mesh_self_intersections']=cached_mesh['intersection_check']
            continue
        log('Meshing at %.1f mm absolute deflection...' % deflection)
        # Remove cached triangulation: each refinement is independently generated.
        clean=shape.cleaned()
        angular=PROPOSED['mesh_angular_deflection_rad']*math.sqrt(deflection/max(PROPOSED['mesh_deflections_mm']))
        raw_mesh=MeshPart.meshFromShape(Shape=clean,LinearDeflection=deflection,
                    AngularDeflection=angular,Relative=False)
        pts,tris=raw_mesh.Topology
        points=[(p.x/1000,p.y/1000,p.z/1000) for p in pts]
        stats,vertices,faces=mesh_statistics(points,tris)
        # Flip all facets only for an otherwise closed, consistently oriented surface.
        flipped=False
        if stats['watertight_manifold'] and not stats['inconsistent_edge_orientations'] and stats['signed_volume_m3']<0:
            faces=[(a,c,b) for a,b,c in faces]
            stats,vertices,faces=mesh_statistics(vertices,faces); flipped=True
        stats.update(deflection_mm=deflection,angular_deflection_rad=angular,global_orientation_flip=flipped,
                     relative_volume_error=abs(stats['signed_volume_m3']-volume)/max(volume,1e-30))
        records.append(stats); finest=(vertices,faces)
        data={'stats':stats}
        if deflection==PROPOSED['mesh_deflections_mm'][-1]:
            try:
                check('finest_mesh_self_intersections',not raw_mesh.hasSelfIntersections())
            except Exception as exc:
                checks['finest_mesh_self_intersections']={'status':'NOT_RUN','value':str(exc)}
            data.update(vertices=vertices,faces=faces,intersection_check=checks['finest_mesh_self_intersections'])
        if data.get('intersection_check',{}).get('status')!='NOT_RUN':
            cache.put(stage,data)
    details['mesh_refinement']=records
    fine=records[-1]; prior=records[-2]
    check('refinement_increases_resolution',fine['triangles']>prior['triangles']>records[0]['triangles'],
          [r['triangles'] for r in records])
    check('mesh_topology_all_levels',all(r['watertight_manifold'] and r['connected_components']==1
          and r['genus']==1 and r['inconsistent_edge_orientations']==0 and r['signed_volume_m3']>0 for r in records))
    dv=abs(fine['signed_volume_m3']-prior['signed_volume_m3'])/max(volume,1e-30)
    da=abs(fine['area_m2']-prior['area_m2'])/max(fine['area_m2'],1e-30)
    check('mesh_volume_accuracy_proposed',fine['relative_volume_error']<=PROPOSED['mesh_volume_relative_error_max'],fine['relative_volume_error'])
    check('mesh_refinement_proposed',dv<=PROPOSED['last_two_mesh_volume_relative_change_max'] and
          da<=PROPOSED['last_two_mesh_area_relative_change_max'],{'volume_relative_change':dv,'area_relative_change':da})
    vertices,faces=finest
    mesh_names=['boundary_surface_m.vtk','boundary_surface_m.json']
    if cache.get('mesh_exports') is None:
        export_vtk(out/mesh_names[0],vertices,faces)
        write_json(out/mesh_names[1],{'units':'m','index_base':0,'region':'EV007_plasma_boundary',
                   'vertices':vertices,'triangles':faces,'source_corrected_step_sha256':sha(corrected),
                   'warning':'Candidate mesh; consult g1_report.json before downstream use.'})
        cache.put('mesh_exports',{'written':True},mesh_names)
    # Use the boundary shell, NOT the solid: inside-solid distance can be zero!
    periodicity=cache.get('sampled_periodicity')
    if periodicity is not None:
        checks['sampled_periodicity_proposed']=periodicity
    else:
        shell=shape.Shells[0]
        samples=min(PROPOSED['rotation_sample_count'],len(vertices)); distances=[]
        angle=2*math.pi/PROPOSED['boundary_periods_claimed']
        log('Checking sampled +22.5/-22.5 degree rotational correspondence...')
        for sign in [-1,1]:
            cs=math.cos(angle); sn=sign*math.sin(angle)
            for i in range(samples):
                x,y,z=vertices[(i*len(vertices))//samples]
                p=App.Vector(1000*(cs*x-sn*y),1000*(sn*x+cs*y),1000*z)
                distances.append(Part.Vertex(p).distToShape(shell)[0]/1000)
        dmax=max(distances) if distances else float('inf')
        check('sampled_periodicity_proposed',dmax<=PROPOSED['rotation_sample_distance_m_max'],
              {'max_distance_m':dmax,'samples_per_direction':samples,
               'limitation':'Sampled diagnostic, not exact symmetry or proof of fundamental period 16.'})
        cache.put('sampled_periodicity',checks['sampled_periodicity_proposed'])
    details['elapsed_seconds']=time.monotonic()-started
    if getattr(App,'GuiUp',False):
        import FreeCADGui as Gui
        Gui.activeDocument().activeView().viewAxonometric(); Gui.activeDocument().activeView().fitAll()
        try:
            Gui.updateGui()
            Gui.activeDocument().activeView().saveImage(str(out/'boundary_preview.png'),1280,900,'White')
        except Exception as exc:
            details['preview_warning']=str(exc)
    status='PASS_PROPOSED_NUMERICAL_CHECKS' if all(c['status']=='PASS' for c in checks.values()) else 'REVIEW_REQUIRED'
    details['checkpoint_events']=list(cache.events)
    result={'status':status,'checks':checks,'details':details}
    if all(c['status'] in ['PASS','FAIL'] for c in checks.values()):
        artifacts=export_names+mesh_names
        if (out/'boundary_preview.png').is_file(): artifacts.append('boundary_preview.png')
        cache.put('complete_audit',result,artifacts)
    return result


def run(input_step, output_parent=None, open_results=False):
    source=Path(input_step).expanduser().resolve()
    if not source.is_file(): raise FileNotFoundError(str(source))
    raw=source.read_bytes()
    fixed=corrected_bytes(raw)  # Validate before any output mutation.
    already_corrected=hashlib.sha256(raw).hexdigest()==CORRECTED_SHA256
    parent=Path(output_parent).expanduser().resolve() if output_parent else desktop_directory()/'Tomahawk_G1_Results'
    parent.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix=time.strftime('Run_%Y%m%d_%H%M%S_'),dir=str(parent)))
    corrected=out/'ev007_boundary_units_corrected.step'
    corrected.write_bytes(fixed)
    shutil.copy2(source,out/('input_already_corrected.step' if already_corrected else 'original_ev007_study_boundary_solid.step'))
    if globals().get('__file__') and Path(__file__).is_file():
        shutil.copy2(Path(__file__),out/'tomahawk_g1.py')
    report={'script_version':VERSION,'python_version':platform.python_version(),
            'source_sha256':sha(source),'corrected_step_sha256':sha(corrected),'output_directory':str(out),
            'g1_gate_status':'UNRESOLVED_PENDING_INTERFACE_REVIEW',
            'scope':'Plasma study boundary only; not coils, first wall, blanket or cassette CAD.',
            'correction':{'action':'Already corrected; geometry and units unchanged.' if already_corrected else 'Change STEP length unit from mm to m; coordinates unchanged.',
                          'physical_length_factor':1 if already_corrected else 1000,
                          'physical_volume_factor':1 if already_corrected else 1000000000,
                          'reason':'Known upload stores ~10.5 coordinate radii against metre-scale SIS baseline.',
                          'no_fitting_to_950_m3':True},
            'backup':backup_metadata(source.parent/BACKUP_NAME),
            'proposed_tolerances_not_approved':PROPOSED,
            'still_required':['Approve engineering boundary authority and reference-volume discrepancy.',
                              'Approve coordinate, outward-normal and periodicity conventions.',
                              'Compare against original EV007 boundary coefficients/solver surface.',
                              'Register coil/first-wall/blanket interfaces and any geometry changes.',
                              'Obtain producing/consuming team interface-control review and signatures.']}
    write_json(out/'g1_report.json',report)
    try:
        import FreeCAD
    except ImportError:
        report['cad_audit']={'status':'NOT_RUN_FREECAD_UNAVAILABLE',
            'message':'Unit preparation succeeded in ordinary Python. Run the same script in FreeCAD Python console for native geometry/mesh checks.'}
    else:
        try:
            report['cad_audit']=native_audit(corrected,out)
        except Exception:
            report['cad_audit']={'status':'ERROR','traceback':traceback.format_exc()}
    write_json(out/'g1_report.json',report)
    interface={'status':'DRAFT_UNSIGNED','producer':{'name':'FreeCAD','script_version':VERSION,
                'source_sha256':sha(source),'corrected_step_sha256':sha(corrected)},
               'consumer':{'solver':None,'version':None,'input_hash':None,'run_id':None},
               'coordinates':{'origin':'Input origin retained, no recentering',
                 'axes':'Input x,y,z retained; +phi counterclockwise about +z',
                 'step_units':'m in corrected source; roundtrip units are encoded by exporter',
                 'freecad_and_brep_units':'mm','surface_mesh_units':'m',
                 'cad_mm_to_mesh_m_matrix':[[.001,0,0,0],[0,.001,0,0],[0,0,.001,0],[0,0,0,1]],
                 'mesh_m_to_consumer_transform':None},
               'normals':'Outward only if mesh topology, orientation and self-intersection checks pass.',
               'periodicity':{'claimed_periods':16,'source':'SIS EV007','approval':None},
               'interpolation':None,'uncertainty_treatment':None,'consumer_volume_m3':None,
               'surface_comparison_metrics':None,'approved_tolerances':None,
               'producer_signature':None,'consumer_signature':None,
               'note':'Fill with real solver evidence; this script never grants formal G1 approval.'}
    write_json(out/'g1_interface_review.json',interface)
    save_readable_results(out,report)
    manifest={'algorithm':'sha256','files':{p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    write_json(out/'sha256_manifest.json',manifest)
    with zipfile.ZipFile(out/'Tomahawk_G1_Evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(out.iterdir()):
            if p.is_file() and p.suffix!='.zip': z.write(p,p.name)
    print('\nSaved: '+str(out))
    print('CAD audit: '+report['cad_audit']['status'])
    print('Formal G1: '+report['g1_gate_status'])
    print('Open RESULTS.html to see the saved results.')
    if open_results: show_output_folder(out)
    return out


def main():
    if globals().get('INPUT_STEP'):
        return run(globals()['INPUT_STEP'],globals().get('OUTPUT_PARENT'),open_results=True)
    # A console run without INPUT_STEP offers a file picker, not macro setup.
    try:
        import FreeCAD as App
    except ImportError:
        App=None
    if App is not None and getattr(App,'GuiUp',False):
        from PySide import QtGui
        try:
            from PySide import QtWidgets
        except ImportError:
            QtWidgets=QtGui
        path=QtWidgets.QFileDialog.getOpenFileName(None,'Select EV007 STEP (original or corrected)','','STEP (*.step *.stp)')[0]
        if not path: return None
        return run(path,open_results=True)
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input_step'); parser.add_argument('--output-parent',default=None)
    args=parser.parse_args()
    return run(args.input_step,args.output_parent,open_results=True)


if __name__=='__main__':
    main()
