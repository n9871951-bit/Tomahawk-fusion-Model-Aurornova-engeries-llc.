"""Tomahawk CAD-A1: plain FreeCAD Python assembly builder, not a macro.

Uses the unchanged corrected EV007 STEP. Builds only defined geometry:
16 coil centerlines, 16 optical layout axes, and four candidate CuCrZr cores
with 128 square coolant passages each. No invented vessel or winding pack.
No G1/MHD/transport/thermal re-run and no automatic gate approval.

In FreeCAD's Python console, use runpy.run_path with this file. Files beside
the script are selected automatically; otherwise a file picker is shown.
Standard Python supports --preflight (dimension checks only, never fake CAD).
"""
import argparse
import copy
import hashlib
import html
import json
import math
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
import traceback
import zipfile

VERSION = 'CAD-A1.0'
BASE = Path(__file__).resolve().parent
CORRECTED_SHA = '8317664cb1d897872fa73a4a73255ce7b5a4e32e2f18921a3d09f4dc066d2899'
STEP_NAME = 'ev007_boundary_units_corrected.step'
CONFIG_NAME = 'tomahawk_assembly_config.json'
SCOPE = 'LAYOUT_AND_CASSETTE_CORE_CANDIDATE_NOT_FULL_ENGINEERING_ASSEMBLY'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def json_write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def desktop_directory():
    # Same known-folder API as the previous G1 script; handles OneDrive Desktop.
    if sys.platform == 'win32':
        import ctypes
        import uuid
        from ctypes import wintypes
        guid = (ctypes.c_ubyte * 16).from_buffer_copy(
            uuid.UUID('B4BFCC3A-DB2C-424C-B029-7FE99A87C641').bytes_le)
        shell = ctypes.WinDLL('shell32', use_last_error=True)
        ole = ctypes.WinDLL('ole32', use_last_error=True)
        fn = shell.SHGetKnownFolderPath
        fn.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE,
                       ctypes.POINTER(ctypes.c_void_p)]
        fn.restype = ctypes.c_long
        ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole.CoTaskMemFree.restype = None
        pointer = ctypes.c_void_p()
        try:
            hr = fn(ctypes.byref(guid), 0, None, ctypes.byref(pointer))
            if hr != 0 or not pointer.value:
                raise OSError('Windows Desktop lookup failed: %s' % hr)
            return Path(ctypes.wstring_at(pointer.value))
        finally:
            if pointer.value:
                ole.CoTaskMemFree(pointer)
    try:
        from PySide import QtCore
        result = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.DesktopLocation)
        if result:
            return Path(result)
    except ImportError:
        pass
    result = Path.home() / 'Desktop'
    if result.is_dir():
        return result
    raise RuntimeError('Desktop unavailable. Set OUTPUT_PARENT explicitly.')


def choose_file(name, caption, file_filter):
    local = BASE / name
    if local.is_file():
        return local
    from PySide import QtWidgets
    result = QtWidgets.QFileDialog.getOpenFileName(None, caption, '', file_filter)[0]
    if not result:
        raise RuntimeError('Cancelled; no existing design was changed.')
    return Path(result)


def positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + ' must be a positive finite number.')
    if not math.isfinite(value) or value <= 0:
        raise ValueError(label + ' must be a positive finite number.')


def dimensions(config):
    if config.get('units') != 'm':
        raise ValueError('Config dimensions must use metres.')
    g, c, coils, laser = (config[x] for x in ('geometry', 'cassette', 'coils', 'laser'))
    for key in ('R0_m', 'a_reference_m', 'reference_volume_m3', 'legacy_wall_scale'):
        positive(g[key], key)
    if g['R0_m'] <= g['a_reference_m'] * g['legacy_wall_scale']:
        raise ValueError('Legacy reference cross-section reaches the symmetry axis.')
    n = c['channels_per_cassette']
    if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 512:
        raise ValueError('channels_per_cassette must be an integer in [1, 512].')
    for key in ('face_area_m2', 'square_channel_side_m', 'front_skin_m',
                'interchannel_ligament_m', 'edge_ligament_m', 'rear_cover_m',
                'screening_bay_width_m', 'screening_bay_edge_margin_m'):
        positive(c[key], key)
    if coils['count'] != 16 or laser['count'] != 16:
        raise ValueError('The controlled architecture requires 16 coils and 16 ports.')
    for key in ('radial_semiaxis_m', 'vertical_semiaxis_m'):
        positive(coils[key], key)
    if coils['radial_semiaxis_m'] <= coils['vertical_semiaxis_m']:
        raise ValueError('This ellipse construction expects radial major semiaxis.')
    if coils['winding_pack_section'] is not None or laser['bore_diameter_m'] is not None:
        raise ValueError('Finite winding packs and port bores require the next reviewed implementation.')
    if laser['qualified_launch_vectors'] is not None or c['manifold_geometry'] is not None or c['joining_method'] is not None:
        raise ValueError('This builder cannot silently substitute supplied optics, manifolds or joining geometry. Integrate them explicitly.')
    if any(v is not None for v in config['not_dimensioned'].values()):
        raise ValueError('A previously unspecified component now has data. Extend its CAD implementation before building.')
    angles = laser['poloidal_angles_deg']
    if len(angles) != 16 or sum(x > 0 for x in angles) != 8 or sum(x < 0 for x in angles) != 8:
        raise ValueError('Expect eight upper and eight lower port-location guides.')
    if any(not math.isfinite(x) or abs(x) >= 90 for x in angles):
        raise ValueError('Poloidal guide angles must be finite and strictly within +/-90 degrees.')
    for key in ('axis_inward_length_m', 'axis_outward_length_m'):
        positive(laser[key], key)
    if any(not math.isfinite(x) for x in [laser['phase_deg'],coils['phase_deg'],laser['legacy_reference_phase_deg']]):
        raise ValueError('Azimuth phases must be finite.')
    azimuths = c['azimuths_deg']
    if len(azimuths) != 4 or any(not math.isfinite(a) for a in azimuths):
        raise ValueError('Four finite RF station azimuths required.')
    if len(set(round(a % 360, 8) for a in azimuths)) != 4:
        raise ValueError('RF stations must be distinct.')
    if not math.isfinite(c['mount_radial_offset_from_legacy_wall_m']):
        raise ValueError('Mount offset must be finite.')
    d = c['square_channel_side_m']
    h = n*d + (n-1)*c['interchannel_ligament_m'] + 2*c['edge_ligament_m']
    w = c['face_area_m2'] / h
    t = c['front_skin_m'] + d + c['rear_cover_m']
    result = {
        'height_m': h, 'flow_length_and_face_width_m': w, 'overall_core_thickness_m': t,
        'front_skin_m': c['front_skin_m'], 'rear_cover_m': c['rear_cover_m'],
        'face_area_m2': w*h, 'square_channel_side_m': d, 'channels_per_cassette': n,
        'channel_flow_area_per_cassette_m2': n*d*d,
        'geometric_wetted_area_per_cassette_m2': n*4*d*w,
        'coolant_volume_per_cassette_m3': n*d*d*w,
        'core_metal_volume_per_cassette_m3': w*h*(c['front_skin_m']+d)-n*d*d*w,
        'cover_volume_per_cassette_m3': w*h*c['rear_cover_m'],
        'screening_bay_side_clearance_m': (c['screening_bay_width_m']-w)/2,
        'mount_radius_m': g['R0_m']+g['a_reference_m']*g['legacy_wall_scale']+
                          c['mount_radial_offset_from_legacy_wall_m'],
        'legacy_reference_b_m': g['reference_volume_m3']/(2*math.pi**2*g['R0_m']*g['a_reference_m']),
        'total_channels': len(azimuths)*n,
    }
    result['packing_screen'] = ('PASS' if result['screening_bay_side_clearance_m'] >=
                                c['screening_bay_edge_margin_m'] else 'FAIL')
    # Derived values describe this new CAD candidate; historical thermal gates do not transfer.
    result['physical_performance'] = 'NOT_EVALUATED_NEW_FLOW_LENGTH_AND_PACKING'
    return result


def channel_centers(config, dim):
    c = config['cassette']; d = c['square_channel_side_m']
    return [-dim['height_m']/2+c['edge_ligament_m']+d/2+
            i*(d+c['interchannel_ligament_m']) for i in range(c['channels_per_cassette'])]


def port_guides(config, dim):
    g, laser = config['geometry'], config['laser']
    a = g['a_reference_m']*g['legacy_wall_scale']
    b = dim['legacy_reference_b_m']*g['legacy_wall_scale']
    guides = []
    for i, angle in enumerate(laser['poloidal_angles_deg']):
        phi = math.radians(laser['phase_deg']+i*22.5)
        theta = math.radians(angle)
        r = g['R0_m']+a*math.cos(theta)
        center = (r*math.cos(phi), r*math.sin(phi), b*math.sin(theta))
        normal = (math.cos(theta)/a*math.cos(phi), math.cos(theta)/a*math.sin(phi), math.sin(theta)/b)
        norm = math.sqrt(sum(x*x for x in normal)); normal = tuple(x/norm for x in normal)
        inside = tuple(x-laser['axis_inward_length_m']*n for x,n in zip(center,normal))
        outside = tuple(x+laser['axis_outward_length_m']*n for x,n in zip(center,normal))
        guides.append({'id':i+1, 'toroidal_deg':laser['phase_deg']+i*22.5,
                       'poloidal_deg':angle, 'ring':'UPPER' if angle > 0 else 'LOWER',
                       'station_m':center, 'normal_outward':normal, 'start_m':inside, 'end_m':outside,
                       'status':'LAYOUT_GUIDE_NOT_QUALIFIED_LASER_VECTOR'})
    return guides


def segment_box_distance(start, end, lower, upper):
    """Exact piecewise-quadratic minimum distance of a line segment to an AABB."""
    delta=[b-a for a,b in zip(start,end)]; breaks={0.,1.}
    for a,v,lo,hi in zip(start,delta,lower,upper):
        if v:
            for bound in (lo,hi):
                t=(bound-a)/v
                if 0<t<1: breaks.add(t)
    breaks=sorted(breaks); candidates=list(breaks)
    for left,right in zip(breaks,breaks[1:]):
        middle=(left+right)/2; numerator=0.; denominator=0.
        for a,v,lo,hi in zip(start,delta,lower,upper):
            value=a+middle*v
            boundary=lo if value<lo else (hi if value>hi else None)
            if boundary is not None:
                numerator+=v*(a-boundary); denominator+=v*v
        if denominator:
            candidates.append(max(left,min(right,-numerator/denominator)))
    return math.sqrt(min(sum(max(lo-(a+t*v),0.,(a+t*v)-hi)**2
                             for a,v,lo,hi in zip(start,delta,lower,upper)) for t in candidates))


def layout_checks(config, dim):
    """Analytic reference-layout checks. No material thickness or laser bore implied.

    Coil-plane distance is a conservative lower bound to each zero-thickness
    ellipse curve. Cassette checks use the enclosing rectangular core+cover box,
    so coolant voids cannot create an artificially favorable clearance.
    """
    guides=port_guides(config,dim); coil=config['coils']; g=config['geometry']
    plane_distances=[]; cassette_distances=[]
    for p in guides:
        for i in range(16):
            phi=math.radians(coil['phase_deg']+i*22.5)
            normal=(-math.sin(phi),math.cos(phi),0.)
            sa=sum(x*n for x,n in zip(p['start_m'],normal))
            sb=sum(x*n for x,n in zip(p['end_m'],normal))
            plane_distances.append(0. if sa*sb<=0 else min(abs(sa),abs(sb)))
        for angle in config['cassette']['azimuths_deg']:
            phi=math.radians(angle)
            def local(p):
                return [p[0]*math.cos(phi)+p[1]*math.sin(phi)-dim['mount_radius_m'],
                        -p[0]*math.sin(phi)+p[1]*math.cos(phi),p[2]]
            w=dim['flow_length_and_face_width_m']; h=dim['height_m']
            cassette_distances.append(segment_box_distance(local(p['start_m']),local(p['end_m']),
                [0,-w/2,-h/2],[dim['overall_core_thickness_m'],w/2,h/2]))
    baseline=copy.deepcopy(config)
    baseline['laser']['phase_deg']=config['laser']['legacy_reference_phase_deg']
    intersections=[]
    for p in port_guides(baseline,dim):
        # Exact line/ellipse roots for the same-azimuth reference coil only.
        matches=[i for i in range(16) if abs((p['toroidal_deg']-(coil['phase_deg']+i*22.5)+180)%360-180)<1e-8]
        if not matches: continue
        phi=math.radians(p['toroidal_deg']); s=p['start_m']; e=p['end_m']
        r=s[0]*math.cos(phi)+s[1]*math.sin(phi)-g['R0_m']; z=s[2]
        dr=(e[0]-s[0])*math.cos(phi)+(e[1]-s[1])*math.sin(phi); dz=e[2]-s[2]
        a=coil['radial_semiaxis_m']; b=coil['vertical_semiaxis_m']
        A=(dr/a)**2+(dz/b)**2; B=2*(r*dr/a**2+z*dz/b**2); C=(r/a)**2+(z/b)**2-1
        discriminant=B*B-4*A*C
        roots=[(-B+sign*math.sqrt(max(0.,discriminant)))/(2*A) for sign in (-1,1)] if discriminant>=0 and A>0 else []
        if any(0<=t<=1 for t in roots): intersections.append(p['id'])
    lower_bound=min(plane_distances); box_clearance=min(cassette_distances)
    return {'scope':'STRAIGHT_LAYOUT_GUIDES_VS_REFERENCE_COILS_AND_CORE_ENVELOPES_ONLY',
            'legacy_phase_deg':baseline['laser']['phase_deg'],
            'legacy_coplanar_guide_intersections':intersections,
            'candidate_phase_deg':config['laser']['phase_deg'],
            'toroidal_spacing_deg':22.5,
            'candidate_min_coil_plane_distance_lower_bound_m':lower_bound,
            'candidate_min_guide_to_cassette_box_distance_m':box_clearance,
            'candidate_guide_screen':'PASS' if lower_bound>1e-6 and box_clearance>1e-6 else 'FAIL_OR_INCONCLUSIVE',
            'limitations':'No bore, optical envelope, finite winding pack, support, wall/blanket penetration, or dynamic focal validation.'}


class ShapeCache:
    """Content-addressed component cache. Never opens or overwrites old FCStd files.

    Each component has its own input contract; changing cassette sizes does not
    rebuild the boundary or coils. Hashes, code and kernel versions are checked.
    """
    def __init__(self, root, out, environment):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.out = Path(out); self.environment = environment; self.events = []

    def key(self, stage, params):
        return digest({'stage':stage, 'params':params, 'environment':self.environment})

    def event(self, stage, status, **extra):
        item = {'stage':stage, 'action':status, **extra}; self.events.append(item)
        json_write(self.out/'progress.json', self.events)
        print('[Tomahawk CAD] %s: %s' % (stage,status), flush=True)

    def load(self, stage, params):
        key = self.key(stage,params); folder = self.root/key
        if not (folder/'index.json').is_file():
            return None
        try:
            index = json.loads((folder/'index.json').read_text(encoding='utf-8'))
            if index['key'] != key or digest(index['data'])!=index['data_sha256']:
                raise ValueError('key mismatch')
            for name, checksum in index['artifacts'].items():
                if Path(name).name != name or sha(folder/name) != checksum:
                    raise ValueError('artifact mismatch: '+name)
            for name in index['artifacts']:
                shutil.copy2(folder/name, self.out/name)
            self.event(stage,'REUSED_VERIFIED_COMPONENT')
            return index['data']
        except (OSError,ValueError,KeyError,TypeError) as exc:
            self.event(stage,'INVALID_CACHE_RECOMPUTE',reason=str(exc))
            return None

    def save(self, stage, params, data, names):
        key = self.key(stage,params); folder = self.root/key
        folder.mkdir(exist_ok=True)
        # Only write generated cache artifacts. Never delete or replace user source CAD.
        for name in names:
            if Path(name).name != name:
                raise ValueError('Unsafe cache filename')
            temp = folder/(name+'.pending')
            shutil.copy2(self.out/name,temp); os.replace(str(temp),str(folder/name))
        index = {'key':key, 'data':data, 'data_sha256':digest(data), 'artifacts':{name:sha(folder/name) for name in names}}
        json_write(folder/'index.pending',index)
        os.replace(str(folder/'index.pending'), str(folder/'index.json'))
        self.event(stage,'BUILT_AND_CHECKPOINTED')


def shape_info(shape, expected_solids=None):
    if shape.isNull() or not shape.isValid():
        raise ValueError('Native geometry is null or invalid. No PASS assigned.')
    if expected_solids is not None and len(shape.Solids) != expected_solids:
        raise ValueError('Unexpected solid count: %d != %d' % (len(shape.Solids), expected_solids))
    if expected_solids:
        if any(not s.isClosed() for s in shape.Solids):
            raise ValueError('Open solid encountered.')
    shape.check(True)  # OCC BOP check raises on native errors.
    return {'solids':len(shape.Solids), 'faces':len(shape.Faces), 'edges':len(shape.Edges),
            'volume_m3':shape.Volume/1e9, 'valid':True}


def native_build(config, dim, source, out, cache_root):
    import FreeCAD as App
    import Part
    env = {'script_sha256':sha(Path(__file__)), 'freecad':list(App.Version()),
           'occ':str(getattr(Part,'OCC_VERSION','unknown')), 'python':platform.python_version()}
    cache = ShapeCache(cache_root,out,env)
    mm = lambda p: App.Vector(*(1000*x for x in p))
    doc = App.newDocument('Tomahawk_CAD_A1_'+str(time.time_ns()))
    groups = {name:doc.addObject('App::DocumentObjectGroup',name) for name in
              ['Plasma_Reference','Coil_Centerlines','Optical_Layout_Guides','RF_Cassette_Candidates','Legacy_Wall_Datum','Legacy_Port_Comparison']}
    objects = []; report = {'scope':SCOPE, 'components':{}, 'native_freecad_executed':True,
                            'g1_status':'NOT_REASSESSED_USE_SEPARATE_G1_EVIDENCE', 'warnings':[]}

    def feature(name,shape,group,status,color,visible=True,transparency=0):
        obj=doc.addObject('Part::Feature',name); obj.Shape=shape
        obj.addProperty('App::PropertyString','DesignStatus','Provenance'); obj.DesignStatus=status
        obj.addProperty('App::PropertyString','InputRevision','Provenance'); obj.InputRevision=config['revision']
        groups[group].addObject(obj); objects.append(obj)
        if App.GuiUp:
            obj.ViewObject.ShapeColor=color; obj.ViewObject.LineColor=color
            obj.ViewObject.Transparency=transparency; obj.ViewObject.Visibility=visible
        return obj

    def stage(name, params, factory, counts):
        previous=cache.load(name,params)
        if previous is not None:
            return {k:Part.read(str(out/(name+'_'+k+'.brep'))) for k in counts},previous
        shapes=factory(); meta={}; names=[]
        for key, shape in shapes.items():
            meta[key]=shape_info(shape,counts[key])
            filename=name+'_'+key+'.brep'; shape.exportBrep(str(out/filename)); names.append(filename)
        cache.save(name,params,meta,names)
        return shapes,meta

    # Existing EV007 is imported verbatim, without a scale transform or G1 solver re-run.
    shapes, meta=stage('plasma',{'sha256':CORRECTED_SHA},
                       lambda:{'boundary':Part.read(str(source))},{'boundary':1})
    plasma=shapes['boundary']; report['components']['plasma']=meta
    feature('EV007_Unchanged_Study_Boundary',plasma,'Plasma_Reference','IMPORTED_STUDY_BOUNDARY',(.14,.64,.62),True,75)
    if not 100 < plasma.Volume/1e9 < 5000:
        raise ValueError('Imported EV007 volume is not metre-scale. Refusing to rescale silently.')

    g, coil=config['geometry'], config['coils']
    def make_coils():
        edges=[]
        for i in range(16):
            phi=math.radians(coil['phase_deg']+i*22.5)
            center=(g['R0_m']*math.cos(phi),g['R0_m']*math.sin(phi),0)
            major=((g['R0_m']+coil['radial_semiaxis_m'])*math.cos(phi),
                   (g['R0_m']+coil['radial_semiaxis_m'])*math.sin(phi),0)
            minor=(center[0],center[1],coil['vertical_semiaxis_m'])
            edges.append(Part.Ellipse(mm(major),mm(minor),mm(center)).toShape())
        return {'paths':Part.makeCompound(edges)}
    shapes,meta=stage('coil_paths',{'coils':coil,'R0_m':g['R0_m']},make_coils,{'paths':0})
    coilshape=shapes['paths']; report['components']['coil_paths']=meta
    feature('Sixteen_Filament_Paths_No_Winding_Pack',coilshape,'Coil_Centerlines',
            'LEGACY_FIELD_REFERENCE_NOT_FINITE_COIL',(.82,.48,.13))

    guides=port_guides(config,dim)
    shapes,meta=stage('port_guides',{'guides':guides},
                      lambda:{'axes':Part.makeCompound([Part.makeLine(mm(x['start_m']),mm(x['end_m'])) for x in guides])},
                      {'axes':0})
    feature('Sixteen_Port_Axis_Guides_No_Bores',shapes['axes'],'Optical_Layout_Guides',
            'LAYOUT_GUIDE_NOT_QUALIFIED_LASER_VECTOR',(.60,.24,.77))
    report['components']['port_guides']=meta
    json_write(out/'port_layout_guides.json',guides)
    old_config=copy.deepcopy(config)
    old_config['laser']['phase_deg']=config['laser']['legacy_reference_phase_deg']
    old_guides=port_guides(old_config,dim)
    shapes,meta=stage('legacy_port_guides',{'guides':old_guides},
                      lambda:{'axes':Part.makeCompound([Part.makeLine(mm(x['start_m']),mm(x['end_m'])) for x in old_guides])},
                      {'axes':0})
    feature('Legacy_Zero_Phase_Guides_COMPARISON_ONLY',shapes['axes'],'Legacy_Port_Comparison',
            'SUPERSEDED_STRAIGHT_GUIDE_LAYOUT_COMPARISON_NOT_ACTUAL_LASER_RAYS',(.8,.18,.18),False)
    report['analytic_guide_comparison']=layout_checks(config,dim)

    # A reference surface only: no wall thickness, no mapping to EV007 is implied.
    def make_wall_datum():
        a=g['a_reference_m']*g['legacy_wall_scale']; b=dim['legacy_reference_b_m']*g['legacy_wall_scale']
        edge=Part.Ellipse(mm((g['R0_m']+a,0,0)),mm((g['R0_m'],0,b)),mm((g['R0_m'],0,0))).toShape()
        return {'surface':edge.revolve(App.Vector(0,0,0),App.Vector(0,0,1),360)}
    shapes,meta=stage('legacy_wall',{'geometry':g},make_wall_datum,{'surface':0})
    feature('Legacy_1_12_Scaled_Wall_DATUM_ONLY',shapes['surface'],'Legacy_Wall_Datum',
            'LEGACY_REFERENCE_NOT_ENGINEERED_WALL',(.55,.58,.63),False,85)
    report['components']['legacy_wall']=meta

    c=config['cassette']; width=dim['flow_length_and_face_width_m']; height=dim['height_m']
    side=c['square_channel_side_m']; skin=c['front_skin_m']; rear=c['rear_cover_m']
    def make_cassette():
        body=Part.makeBox((skin+side)*1000,width*1000,height*1000,mm((0,-width/2,-height/2)))
        channels=[]; tools=[]; epsilon=0.00001
        for z in channel_centers(config,dim):
            channels.append(Part.makeBox(side*1000,width*1000,side*1000,mm((skin,-width/2,z-side/2))))
            # Grooves open on the rear for machining; cover is a separate part.
            tools.append(Part.makeBox((side+epsilon)*1000,(width+2*epsilon)*1000,side*1000,
                                      mm((skin,-width/2-epsilon,z-side/2))))
        core=body.cut(Part.makeCompound(tools))
        cover=Part.makeBox(rear*1000,width*1000,height*1000,mm((skin+side,-width/2,-height/2)))
        return {'core':core,'cover':cover,'coolant':Part.makeCompound(channels)}
    # Exclude placement from the expensive template's cache key.
    template_params={k:c[k] for k in ['face_area_m2','channels_per_cassette','square_channel_side_m',
                                     'front_skin_m','interchannel_ligament_m','edge_ligament_m','rear_cover_m']}
    shapes,meta=stage('cassette_template',template_params,make_cassette,
                      {'core':1,'cover':1,'coolant':c['channels_per_cassette']})
    report['components']['cassette_template']=meta
    for key, expected in [('core',dim['core_metal_volume_per_cassette_m3']),
                          ('cover',dim['cover_volume_per_cassette_m3']),
                          ('coolant',dim['coolant_volume_per_cassette_m3'])]:
        if abs(meta[key]['volume_m3']/expected-1)>1e-7:
            raise ValueError('Cassette analytic/native volume mismatch: '+key)
    cassette_objects=[]; cassette_shapes=[]
    for number, azimuth in enumerate(c['azimuths_deg'],1):
        station=[]
        for key,color,visible in [('core',(.78,.43,.25),True),('cover',(.63,.69,.74),True),
                                  ('coolant',(.15,.53,.89),False)]:
            shape=shapes[key].copy()
            shape.translate(mm((dim['mount_radius_m'],0,0)))
            shape.rotate(App.Vector(0,0,0),App.Vector(0,0,1),azimuth)
            obj=feature('RF%02d_%s_CANDIDATE'%(number,key),shape,'RF_Cassette_Candidates',
                        'NEW_PACKAGING_CANDIDATE_NOT_PRESSURE_QUALIFIED',color,visible)
            obj.addProperty('App::PropertyString','MaterialIntent','Provenance')
            obj.MaterialIntent='water domain' if key=='coolant' else 'CuCrZr candidate; no material certification'
            if key!='coolant':
                cassette_objects.append(obj); station.append(shape)
        cassette_shapes.append(Part.makeCompound(station))
    # New assembly checks only. Coils are curves, so clearance is NOT casing clearance.
    interface_params={'config':config,'source':CORRECTED_SHA}
    interfaces=cache.load('interface_checks',interface_params)
    if interfaces is None:
        interfaces={'cassette_to_plasma':[], 'coil_centerline_to_cassette':[],
                    'scope':'LOCAL_CORE_AND_REFERENCE_PATH_CHECKS_NOT_FULL_PLANT_CLEARANCE'}
        for index,shape in enumerate(cassette_shapes,1):
            overlap=shape.common(plasma).Volume/1e9
            distance=shape.distToShape(plasma)[0]/1000
            coil_distance=shape.distToShape(coilshape)[0]/1000
            interfaces['cassette_to_plasma'].append({'station':index,'overlap_m3':overlap,
                                                      'distance_m':distance,'status':'PASS' if overlap<1e-9 and distance>1e-6 else 'FAIL'})
            interfaces['coil_centerline_to_cassette'].append({'station':index,'distance_m':coil_distance,
                                                             'status':'REFERENCE_DISTANCE_ONLY_NO_PACK_SECTION'})
        cache.save('interface_checks',interface_params,interfaces,[])
    report['interfaces']=interfaces
    report['geometry_checks_status']=('FAIL' if dim['packing_screen']=='FAIL' or
        report['analytic_guide_comparison']['candidate_guide_screen']!='PASS' or
        any(x['status']=='FAIL' for x in interfaces['cassette_to_plasma']) else 'PASS_LIMITED_SCOPE')
    report['warnings'] += [
        'This is a partial assembly: vessel, blanket, finite coils, port bores, headers and RF face stack are not dimensioned.',
        'Legacy wall datum and optical normals are not CAD-to-equilibrium or laser-absorption closure.',
        'Cassette is a grooved core plus separate cover; bond/weld geometry and pressure containment are not modeled.',
        'Channel entrances/exits terminate at the two core sides. No external manifold or pumping loss prediction.',
        'New flow length and ligament/cover dimensions invalidate automatic inheritance of old cassette pass rates.'
    ]
    doc.recompute()
    exports=cache.load('assembly_exports',interface_params)
    if exports is None:
        # Make a fresh FCStd each run; STEP contains physical candidates plus clearly named reference objects.
        doc.saveAs(str(out/'Tomahawk_CAD_A1.FCStd'))
        Part.export([o for o in objects if o.ViewObject.Visibility] if App.GuiUp else
                    [o for o in objects if not o.Name.endswith('coolant_CANDIDATE') and 'DATUM' not in o.Name and 'COMPARISON' not in o.Name],
                    str(out/'Tomahawk_CAD_A1_REFERENCE_ASSEMBLY.step'))
        Part.export(cassette_objects,str(out/'RF_Four_Cores_And_Covers_CANDIDATE.step'))
        Part.makeCompound([shapes['core'],shapes['cover']]).exportStep(str(out/'RF_Local_Core_And_Cover_CANDIDATE.step'))
        shapes['coolant'].exportStep(str(out/'RF_Local_128_Coolant_Domains.step'))
        names=['Tomahawk_CAD_A1.FCStd','Tomahawk_CAD_A1_REFERENCE_ASSEMBLY.step',
               'RF_Four_Cores_And_Covers_CANDIDATE.step','RF_Local_Core_And_Cover_CANDIDATE.step',
               'RF_Local_128_Coolant_Domains.step']
        cache.save('assembly_exports',interface_params,{'files':names},names)
    if App.GuiUp:
        import FreeCADGui as Gui
        view=Gui.activeDocument().activeView(); view.viewAxonometric(); view.fitAll()
        try:
            view.saveImage(str(out/'FreeCAD_Assembly.png'),1600,1000,'White')
        except Exception as exc:
            report['warnings'].append('Screenshot unavailable: '+str(exc))
    report['checkpoint_events']=cache.events
    return report


def save_summary(out, report, dim, config):
    missing=', '.join(config['not_dimensioned'])
    rows=''.join('<tr><td>%s</td><td>%s</td></tr>'%(html.escape(k),html.escape(str(v))) for k,v in dim.items())
    preview='<img src="FreeCAD_Assembly.png" alt="Native FreeCAD assembly">' if (out/'FreeCAD_Assembly.png').exists() else ''
    text='''<!doctype html><html lang="en"><meta charset="utf-8"><title>Tomahawk CAD-A1</title>
    <style>body{font:16px system-ui;color:#173447;max-width:1000px;margin:35px auto;padding:15px}
    td,th{border:1px solid #cad7df;padding:9px;text-align:left}table{border-collapse:collapse}img{max-width:100%%}
    pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>Tomahawk CAD-A1</h1>
    <p>Scope: %s</p><p>Run status: <strong>%s</strong></p>%s
    <p>Unchanged EV007 + 16 coil paths + 16 port guides + four square-channel cassette candidates.</p>
    <p>Not yet dimensioned: %s.</p><h2>Dimensions (metres unless noted)</h2><table>%s</table>
    <h2>Run record</h2><pre>%s</pre><p>No new thermal, pressure, confinement or G1 pass is claimed.</p></html>''' % (
        SCOPE,html.escape(report['status']),preview,html.escape(missing),rows,
        html.escape(json.dumps(report,indent=2)))
    (out/'RESULTS.html').write_text(text,encoding='utf-8')


def run(source, config_path, output_parent=None, preflight=False, open_folder=True):
    source=Path(source).resolve(); config_path=Path(config_path).resolve()
    if sha(source)!=CORRECTED_SHA:
        raise ValueError('Select the reviewed ev007_boundary_units_corrected.step. No geometry or unit guessing.')
    config=json.loads(config_path.read_text(encoding='utf-8')); dim=dimensions(config)
    parent=Path(output_parent) if output_parent else desktop_directory()/'Tomahawk_CAD_Assembly'
    parent.mkdir(parents=True,exist_ok=True)
    out=Path(tempfile.mkdtemp(prefix='CAD_A1_'+time.strftime('%Y%m%d_%H%M%S')+'_',dir=str(parent)))
    report={'version':VERSION,'status':'STARTED','scope':SCOPE,'input_sha256':sha(source),
            'config_sha256':sha(config_path),'script_sha256':sha(Path(__file__)),
            'native_freecad_executed':False,'output_folder':str(out)}
    shutil.copy2(source,out/STEP_NAME); shutil.copy2(config_path,out/CONFIG_NAME)
    json_write(out/'dimensions.json',dim)
    json_write(out/'layout_checks.json',layout_checks(config,dim))
    json_write(out/'channel_interfaces_local_m.json',{
        'frame':'cassette local: x radial outward; y along flow; z vertical; metres',
        'station_placement':'translate x by mount_radius_m, then rotate about global z by station azimuth',
        'mount_radius_m':dim['mount_radius_m'],'station_azimuths_deg':config['cassette']['azimuths_deg'],
        'domains':[{'channel':i+1,'inlet_center_m':[config['cassette']['front_skin_m']+
                         config['cassette']['square_channel_side_m']/2,-dim['flow_length_and_face_width_m']/2,z],
                    'outlet_center_m':[config['cassette']['front_skin_m']+
                         config['cassette']['square_channel_side_m']/2,dim['flow_length_and_face_width_m']/2,z],
                    'inlet_outward_normal':[0,-1,0],'outlet_outward_normal':[0,1,0],
                    'opening_area_m2':config['cassette']['square_channel_side_m']**2}
                   for i,z in enumerate(channel_centers(config,dim))],
        'status':'GEOMETRIC_INTERFACES_ONLY_NO_BOUNDARY_CONDITIONS_OR_CFD_MESH'})
    try:
        if preflight:
            report['status']='DIMENSION_PREFLIGHT_ONLY'
            report['packing_screen']=dim['packing_screen']
        else:
            report.update(native_build(config,dim,source,out,parent/'Component_Checkpoints'))
            report['status']='COMPLETED_CANDIDATE_ASSEMBLY'
    except Exception as exc:
        report['status']='FAILED_NO_APPROVAL'; report['error']=str(exc)
        report['traceback']=traceback.format_exc()
    json_write(out/'assembly_report.json',report); save_summary(out,report,dim,config)
    manifest={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    json_write(out/'manifest_sha256.json',manifest)
    with zipfile.ZipFile(out/'Tomahawk_CAD_A1_Results.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for filename in list(manifest)+['manifest_sha256.json']:
            archive.write(out/filename,filename)
    print('\n%s\nResults: %s\n'%(report['status'],out),flush=True)
    if open_folder:
        try:
            if sys.platform=='win32': os.startfile(str(out))
            else:
                from PySide import QtCore,QtGui
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(out)))
        except Exception:
            pass
    return out, report


def main():
    try:
        import FreeCAD
        has_cad=True
    except ImportError:
        has_cad=False
    if has_cad:
        source=Path(globals()['INPUT_STEP']) if globals().get('INPUT_STEP') else choose_file(STEP_NAME,'Select corrected EV007 STEP','STEP (*.step *.stp)')
        config=Path(globals()['CONFIG_PATH']) if globals().get('CONFIG_PATH') else choose_file(CONFIG_NAME,'Select assembly config','JSON (*.json)')
        run(source,config,globals().get('OUTPUT_PARENT'),open_folder=True)
    else:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--preflight',action='store_true')
        parser.add_argument('--input-step',type=Path,default=BASE/STEP_NAME)
        parser.add_argument('--config',type=Path,default=BASE/CONFIG_NAME)
        parser.add_argument('--output-parent',type=Path)
        args=parser.parse_args()
        if not args.preflight:
            parser.error('FreeCAD is not installed in this interpreter. Run in FreeCAD Python console; --preflight checks dimensions only.')
        run(args.input_step,args.config,args.output_parent,preflight=True,open_folder=False)


if __name__=='__main__':
    main()
