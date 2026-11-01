# TF48 / PF MGRID specification reconciliation

## Result

The two branches now use the same numerical MGRID grid and mode. They do not
and must not use the same coil physics metadata.

| Specification | TF48 companion | PF companion | Reconciled? |
|---|---:|---:|---|
| R range | 4.0…11.0 m | 4.0…11.0 m | Yes |
| Z range | -3.5…+3.5 m | -3.5…+3.5 m | Yes |
| Toroidal planes (`KP`) | 36 | 36 | Yes |
| Radial points (`IR`) | 201 | 201 | Yes |
| Vertical points (`JZ`) | 201 | 201 | Yes |
| MGRID mode | `S` | `S` | Yes |
| Stellarator symmetry | No | No | Yes |
| Coil branch | 48 physical TF coils | six PF groups | No — intentional |
| Field periodicity (`nfp`) | 16 | 1 | No — intentional |
| Target field | 16 T TF axis target | no PF 16 T target | No — intentional |

## Branch controls that remain distinct

- TF48 uses three exact base-coil chunks with `periods 16`, representing the
  verified 48 physical TF coils. Its canonical native schedule is -125,000
  A/turn and its direct edge-ripple preflight is 0.7539178029%, which is below
  the strict 1.0% limit.
- PF uses the supplied six groups `PF_L_IN`, `PF_L_OUT`, `PF_M_IN`,
  `PF_M_OUT`, `PF_U_IN`, and `PF_U_OUT`: 578 closed 128-point loops in total,
  `periods 1`, and the six supplied currents. The prior PF reference reports
  about 0.5050786776 T at the reference axis; it is not a 16 T TF field.
- The PF three-part package splits the real PF groups as lower, middle, and
  upper pairs: 190, 198, and 190 loops. It does not relabel the PF branch as
  48/16/16 T. Its assembled output remains a six-group PF MGRID.

## Downstream meaning

The shared grid makes later field-array reconciliation well-defined. Total
field assembly still requires the native TF48 16 T MGRID plus the six-group PF
MGRID, followed by the final G1-boundary, free-boundary, VMEC/DESC, and other
downstream gates. A PF file with `nfp=16` or a fabricated 16 T PF target would
be a specification error.

The native XGRID executable is not embedded in these handoffs. The three TF
and three PF notebooks discover the authorized Kaggle XGRID runtime dataset,
run independently, and fail closed unless a valid native MGRID is produced.
