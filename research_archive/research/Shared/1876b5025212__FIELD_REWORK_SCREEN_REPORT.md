# Tomahawk field rework screen for the D–D cycle

Status: **field-target screen, not a coil design or safety certification**

## Control point

Magnetic pressure is `p_B = B²/(2 μ₀)` and beta is `p_plasma/p_B`. The existing 14 T value is the plasma-axis field; 35 T is the peak conductor/coil field and cannot be substituted for the plasma field without a new Biot–Savart solution.

## Reference D–D state

At 20 keV, baseline density, and 3 s product retention: plasma pressure is **0.505626 MPa**, beta at 14 T is **0.00648355**, and beta at 35 T would be **0.00103737** if 35 T were actually the plasma field.

## 5-GW conditional states

Among scanned states producing at least 5 GW of D–D-cycle power, the lowest field target for beta ≤ 5% is **19.8195 T on axis** at T=30 keV, density multiplier=10, retention=10 s. A simple linear scaling of the current 14 T-axis/35 T-coil pair would imply about **49.5488 T peak coil field**, but that is only a screening inference.
The corresponding lowest beta ≤ 10% field target is **14.0145 T** at T=30 keV, density multiplier=10, retention=10 s.
At that 5-GW screening state, the He-3 reaction time is about **93.0772 s**. Keeping the reduced-order He-3 secondary-burn fraction below 1% would require a residence/exhaust time below about **0.940174 s**; below 0.1% would require about **0.0931704 s**.

## Required redesign decision

A stronger field is necessary for high-density D–D states, but it is not sufficient to prevent He-3 from reacting. The rework must carry two separate controls:

1. **Field envelope:** solve the actual 48-coil/PF geometry for the selected B0 target, beta margin, ripple, stress, and quench limits.
2. **Product control:** set a He-3 residence-time/exhaust target so the D–He-3 burn fraction is intentional rather than uncontrolled. A stronger field can improve retention, which may increase—not decrease—the chance of secondary reaction.

The next field solve should therefore use `B0_target`, `beta_target`, `n_D`, `T_i/T_e`, and `tau_He3_target` as coupled inputs. It should not simply replace 14 T with an arbitrary immense scalar field.
