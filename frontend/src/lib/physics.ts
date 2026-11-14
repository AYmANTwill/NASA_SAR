/**
 * Physical constants of the instruments (not measurements).
 * Sources: NISAR mission (JPL/ISRO) L-band 1.257 GHz; Sentinel-1 C-band 5.405 GHz.
 * λ = c / f.
 */
const C = 299_792_458; // m/s
export const L_BAND_HZ = 1.257e9;
export const C_BAND_HZ = 5.405e9;
/** Wavelengths in centimetres. */
export const L_BAND_CM = (C / L_BAND_HZ) * 100;
export const C_BAND_CM = (C / C_BAND_HZ) * 100;
