# Tomahawk Chemical Fuel-Cycle Integration — Rev 0.1

AuroraNova Energies LLC | Protected black-box interface | 18 September 2026

## Purpose

This overlay adds a parameterized interface for a previously omitted proprietary
fuel-cycle process without requiring disclosure of its recipe. It is an
accounting interface, not a claim that the process has been reconstructed or
validated.

The existing Tomahawk baseline already contains:

- a neutron-transport tritium-breeding term;
- TBR and time-dependent tritium-inventory equations;
- recovery, processing, permeation, maintenance, and decay losses; and
- `P_fuel_cycle` / `P_tritium_processing` plant-load terms.

This overlay supplies the missing process boundary between the blanket/exhaust
streams and usable D-T fuel injection.

## Physics boundary that must remain locked

Chemistry can rearrange, separate, purify, transport, store, and recycle nuclei.
It cannot create new tritium nuclei. Newly created tritium must enter through a
nuclear source, normally the lithium-bearing blanket reactions represented by
the neutronics model. The chemical subsystem can then determine how much of that
source becomes usable fuel.

Accordingly, the model uses this distinction:

```text
3-D neutronics -> nuclear tritium source -> chemical capture/separation/
purification/storage -> usable fuel return -> D-T injection
```

If the private process is actually a chemical recovery/separation/recycling
loop, it can be integrated here without exposing implementation-level IP. If it
is being described as creating tritium with no nuclear source, the model must
stop with `INVALID_CHEMICAL_NUCLEAR_BREEDING_CLAIM` rather than silently accept
that result.

## Coupled reduced-order equations

For each species `s` in `{D,T}`:

```text
eta_chem,s = eta_capture,s * eta_separation,s * eta_purification,s

F_process,s = F_recovery,s + F_other_process_feed,s

F_bred_to_process,T = R_T_bred * eta_bred_delivery,T

F_return,s(t + tau_process) = eta_chem,s *
                               [F_process,s + F_bred_to_process,s]

F_usable,s(t) = F_return,s(t) + F_direct_makeup,s

F_chem_loss,s = F_process,s + F_bred_to_process,s -
                 F_return,s - F_delivery_loss,s
```

The species inventory is then coupled to the host burn model as:

```text
dM_D/dt = F_usable,D - F_burn,D - L_D,other

dM_T/dt = F_usable,T - F_burn,T - lambda_T*M_T
          - L_T,permeation - L_T,other
          - L_T,recovery_feed_if_already_debited
```

The existing host equation must not also subtract the same processing stream.
The adapter reports a `double_counting_guard` and identifies whether the
recovery feed was already removed from the host inventory.

The process does not define a new nuclear TBR. It reports:

```text
usable_T_fraction_of_bred = F_usable,T_from_bred / R_T_bred
fuel_supply_ratio_T = F_usable,T / F_burn,T
```

`fuel_supply_ratio_T >= 1` is only a supply screen. Tomahawk Gate 6 still
requires a realized, uncertainty-qualified 3-D neutronics TBR and a positive
time-dependent inventory after all losses and reserves.

## Required protected inputs

The recipe itself may remain outside the model. The model requires only the
following performance-level quantities:

| Input | Unit | Why it is needed |
|---|---:|---|
| nuclear tritium production from neutronics | kg/s | Proves the source of new T nuclei |
| D/T process-feed rates | kg/s | Defines the material entering the black box |
| delivery, capture, separation, and purification efficiencies | 0–1 | Computes usable return and process loss |
| processing delay and hold-up | s, kg | Determines transient inventory behavior |
| direct D/T makeup rates | kg/s | Captures external feedstock, if any |
| initial D/T inventory and reserve | kg | Makes positivity test reproducible |
| permeation and other loss rates | kg/s | Prevents false self-sufficiency |
| process auxiliary power and heat | W | Couples the process to plant recirculating power and thermal balance |

The minimum protected disclosure is therefore a signed parameter sheet or a
hash-addressed private file—not the chemical recipe.

## Current status

The historical project record contains the ALSB/FLiBe blanket concepts,
Li-6/Li-7 breeding equations, HTO/HT extraction discussion, and a tritium
extraction/containment block. It does not contain the private process identity,
reaction set, separation method, efficiencies, delay, or power requirement.

Until those performance-level inputs are supplied, the correct status is:

```text
CHEMICAL_FUEL_CYCLE_INTERFACE_ADDED
PROCESS_RECONSTRUCTION = OPEN
TRITIUM_SELF_SUFFICIENCY = NOT DEMONSTRATED
NET_ELECTRIC_RESULT = NOT UPDATED
```

The accompanying JSON template intentionally uses `null` for unknown values.
The accompanying adapter refuses to convert missing values into optimistic
assumptions.

## IP handling

Use a private process identifier and optional hash in the public model:

```text
process_id: AN-CFCP-001
recipe_disclosure: PROTECTED_BLACK_BOX
recipe_hash: supplied separately, never embedded in public outputs
```

Public reports should expose only mass-balance outputs, uncertainty, and gate
status. They should not expose the process recipe, operational conditions, or
construction details.

