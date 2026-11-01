#pragma once
#include <array>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

struct Thermal {
  std::vector<std::array<double,7>> rows;
  double W0=0, A0=0, Pa0=0, B0=0, ta0=0;
  double tauE, sync0, syncExponent, ext, retention, delayExponent;
  static double reactivity(double T) {
    if (!(T>=0.2 && T<=100)) throw std::runtime_error("D-T fit temperature outside [0.2,100] keV");
    const double theta=T/(1-T*(1.51361e-2+T*(4.60643e-3-1.06750e-4*T))/(1+T*(7.51886e-2+T*(1.35000e-2+1.36600e-5*T))));
    const double xi=std::cbrt(34.3827*34.3827/(4*theta));
    return 1e-6*1.17302e-9*theta*std::sqrt(xi/(1.124656e6*T*T*T))*std::exp(-3*xi);
  }
  double birth(double scale) const {
    double total=0;
    for (const auto& r:rows) total+=r[3]*r[3]*reactivity(r[5]*scale)*r[1]*3.5*1.602176634e-13/1e6;
    return total;
  }
  void load(const std::string& path) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("Cannot open radial profile: "+path);
    std::string line; std::getline(f,line);
    while (std::getline(f,line)) {
      if(line.empty()) continue;
      std::stringstream ss(line); std::array<double,7> r{};
      for (auto& v:r) {std::string cell; if(!std::getline(ss,cell,',')) throw std::runtime_error("Bad profile row"); v=std::stod(cell); if(!std::isfinite(v)) throw std::runtime_error("Nonfinite profile");}
      for(int k=1;k<7;k++) if(r[k]<=0) throw std::runtime_error("Nonpositive profile value");
      rows.push_back(r);
      W0+=1.5*(r[2]+2*r[3]+r[4])*r[5]*1.602176634e-16*r[1]/1e6;
      A0+=1.5*r[6]*r[1]/1e6;
      B0+=5.35e-37*(2*r[3]+4*r[4])*r[2]*std::sqrt(r[5])*r[1]/1e6;
    }
    if(rows.size()!=48) throw std::runtime_error("Expected 48 source quadrature nodes");
    Pa0=birth(1); ta0=A0/Pa0;
  }
  std::array<double,4> rhs(double W,double A) const {
    if(W<=0 || A< -1e-8) throw std::runtime_error("Unphysical energy");
    const double s=W/W0;
    const double birthPower=retention*birth(s);
    const double dep=A/(ta0*std::pow(s,delayExponent));
    const double loss=W/tauE+B0*std::sqrt(s)+sync0*std::pow(s,syncExponent);
    return {dep+ext-loss,birthPower-dep,birthPower+ext,loss};
  }
};
