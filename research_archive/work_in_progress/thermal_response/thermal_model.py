"""Time-dependent, fixed-profile thermal screen. See MODEL.md for scope."""
from pathlib import Path
import json
import numpy as np
from scipy.integrate import solve_ivp

KEV_J = 1.602176634e-16
MEV_J = KEV_J * 1000

def reactivity(T):
    T = np.asarray(T, dtype=float)
    if not np.isfinite(T).all() or np.any(T < 0.2) or np.any(T > 100):
        raise ValueError('D-T fit temperature outside [0.2, 100] keV')
    c1,c2,c3,c4,c5,c6,c7 = (1.17302e-9,1.51361e-2,7.51886e-2,4.60643e-3,1.35000e-2,-1.06750e-4,1.36600e-5)
    theta = T/(1-T*(c2+T*(c4+T*c6))/(1+T*(c3+T*(c5+T*c7))))
    xi = (34.3827**2/(4*theta))**(1/3)
    return 1e-6*c1*theta*np.sqrt(xi/(1.124656e6*T**3))*np.exp(-3*xi)

class ThermalModel:
    def __init__(self, directory, overrides=None):
        self.directory = Path(directory)
        self.settings = json.loads((self.directory/'settings.json').read_text())
        self.settings.update(overrides or {})
        p = np.loadtxt(self.directory/'radial_profile.csv', delimiter=',', skiprows=1)
        self.rho,self.dv,self.ne,self.nd,self.nhe,self.T0,self.pfast = p.T
        if not np.isfinite(p).all() or np.any(p[:,1:] <= 0):
            raise ValueError('Invalid input profile')
        self.ni = 2*self.nd+self.nhe
        self.W0 = float(1.5*np.sum((self.ne+self.ni)*self.T0*KEV_J*self.dv)/1e6)
        self.A0 = float(1.5*np.sum(self.pfast*self.dv)/1e6)
        self.Pa0 = self.birth(1.)
        self.ta0 = self.A0/self.Pa0
        self.B0 = float(np.sum(5.35e-37*(2*self.nd+4*self.nhe)*self.ne*np.sqrt(self.T0)*self.dv)/1e6)
        s = self.settings
        if not (s['tau_E_s'] > 0 and 0 <= s['alpha_retention'] <= 1 and s['absorbed_external_MW'] >= 0):
            raise ValueError('Invalid transport, retention or source setting')

    def birth(self, scale):
        return float(np.sum(self.nd**2*reactivity(self.T0*scale)*self.dv)*self.settings['alpha_energy_MeV']*MEV_J/1e6)

    def powers(self, y):
        W,A = float(y[0]),float(y[1])
        if W <= 0 or A < -1e-8:
            raise ValueError('Unphysical thermal/alpha energy')
        scale = W/self.W0
        s = self.settings
        pa = self.birth(scale)
        dep = A/(self.ta0*scale**s['alpha_delay_temperature_exponent'])
        brem = self.B0*np.sqrt(scale)
        sync = s['synchrotron_baseline_MW']*scale**s['synchrotron_temperature_exponent']
        trans = W/s['tau_E_s']
        ext = s['absorbed_external_MW']
        return {'temperature_scale':scale, 'T_peak_keV':float(max(self.T0)*scale),
          'P_fusion_MW':pa*s['fusion_energy_MeV']/s['alpha_energy_MeV'],
          'P_alpha_birth_MW':pa,'P_alpha_deposited_MW':dep,
          'P_alpha_escaped_MW':(1-s['alpha_retention'])*pa,
          'P_external_absorbed_MW':ext,'P_brems_MW':brem,'P_sync_MW':sync,
          'P_transport_MW':trans,'P_loss_MW':brem+sync+trans,
          'self_heating_ratio':dep/(brem+sync+trans)}

    def rhs(self, t, y):
        p = self.powers(y)
        retained = self.settings['alpha_retention']*p['P_alpha_birth_MW']
        return np.array([p['P_alpha_deposited_MW']+p['P_external_absorbed_MW']-p['P_loss_MW'],
                         retained-p['P_alpha_deposited_MW'],
                         retained+p['P_external_absorbed_MW'],p['P_loss_MW']])

    def initial(self, scale=1.):
        # Preserve the supplied fast-alpha reservoir for temperature perturbations.
        return np.array([self.W0*scale,self.A0,0.,0.])

    def solve(self, initial, start=0., stop=None, rtol=1e-9, atol=1e-10, max_step=0.01):
        stop = self.settings['duration_s'] if stop is None else stop
        def lower(t,y): return y[0]/self.W0-self.settings['temperature_scale_min']
        def upper(t,y): return self.settings['temperature_scale_max']-y[0]/self.W0
        lower.terminal=upper.terminal=True
        lower.direction=upper.direction=-1
        sol=solve_ivp(self.rhs,(start,stop),initial,method='Radau',rtol=rtol,atol=atol,
                     events=(lower,upper),max_step=max_step,dense_output=True)
        if not sol.success: raise RuntimeError(sol.message)
        dt=self.settings['output_dt_s']
        times=np.arange(start,float(sol.t[-1])+dt*0.1,dt)
        times=times[times<=sol.t[-1]+1e-12]
        if not len(times) or abs(times[-1]-sol.t[-1])>1e-10: times=np.append(times,sol.t[-1])
        y=sol.sol(times).T
        return times,y,('screening_range_exited' if sol.status==1 else 'completed')

def scenarios(settings):
    tau=settings['tau_E_s']
    return [
      ('reference',{},1.),
      ('temperature_plus_1pct',{},1.01),
      ('temperature_minus_1pct',{},0.99),
      ('confinement_minus_10pct',{'tau_E_s':tau*0.9},1.),
      ('confinement_plus_10pct',{'tau_E_s':tau*1.1},1.),
      ('external_heating_off',{'absorbed_external_MW':0.},1.),
      ('alpha_retention_90pct',{'alpha_retention':0.9},1.),
      ('synch_exponent_2',{'synchrotron_temperature_exponent':2.},1.),
      ('synch_exponent_3',{'synchrotron_temperature_exponent':3.},1.)
    ]
