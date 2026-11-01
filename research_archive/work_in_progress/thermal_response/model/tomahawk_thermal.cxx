#include <bout/physicsmodel.hxx>
#include <fstream>
#include <iomanip>
#include "thermal.hxx"

class TomahawkThermal: public PhysicsModel {
  Field3D W,A,Ein,Eout;
  Thermal physics;
  std::ofstream csv;
  double offset=0, low=0.5, high=2;
  int ix=0, iy=0;
protected:
  int init(bool) override {
    auto& o=Options::root()["thermal"];
    physics.tauE=o["tau_e"].as<double>();
    physics.sync0=o["sync_mw"].as<double>();
    physics.syncExponent=o["sync_exponent"].as<double>();
    physics.ext=o["external_mw"].as<double>();
    physics.retention=o["alpha_retention"].as<double>();
    physics.delayExponent=o["delay_exponent"].as<double>();
    physics.load(o["profile"].as<std::string>());
    if(physics.tauE<=0 || physics.retention<0 || physics.retention>1 || physics.ext<0)
      throw BoutException("Invalid thermal input");
    offset=o["time_offset"].withDefault(0.);
    low=o["scale_min"].withDefault(0.5); high=o["scale_max"].withDefault(2.);
    SOLVE_FOR(W,A,Ein,Eout);
    W=o["initial_w"].as<double>(); A=o["initial_a"].as<double>();
    Ein=o["initial_ein"].withDefault(0.); Eout=o["initial_eout"].withDefault(0.);
    ix=mesh->xstart; iy=mesh->ystart;
    csv.open(o["csv"].as<std::string>(),std::ios::trunc);
    if(!csv) throw BoutException("Cannot create result CSV");
    csv<<"time_s,Wthermal_MJ,Walpha_MJ,Ein_MJ,Eout_MJ\n"<<std::setprecision(17);
    return 0;
  }
  int rhs(BoutReal) override {
    const auto f=physics.rhs(W(ix,iy,0),A(ix,iy,0));
    ddt(W)=f[0]; ddt(A)=f[1]; ddt(Ein)=f[2]; ddt(Eout)=f[3];
    return 0;
  }
  int outputMonitor(BoutReal time,int,int) override {
    const double w=W(ix,iy,0), a=A(ix,iy,0);
    csv<<time+offset<<','<<w<<','<<a<<','<<Ein(ix,iy,0)<<','<<Eout(ix,iy,0)<<'\n';
    csv.flush();
    // A controlled stop at the stated screen range, not a physical stability verdict.
    return (w/physics.W0<low || w/physics.W0>high) ? 1:0;
  }
};
BOUTMAIN(TomahawkThermal);
