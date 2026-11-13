# Data of real measurements used by the samples of the twin

`nwa7034_qvistgaard2026.npz`: the magnetized fragment of the Martian meteorite NWA 7034 measured by polarimetric
neutron imaging at RADEN (J-PARC). From the data of C. Qvistgaard et al., Geochem. Geophys. Geosyst. 27, e2025GC012641
(2026), published by E. B. Naver et al. on DTU Data, doi:10.11583/DTU.30775208, under the license CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/); analysis by C. Qvistgaard. Arrays, unchanged except for units and
axis order (axes x, y, z; y vertical = rotation axis; z = beam at their angle 0):

- `B`: the field reconstructed by the authors (their B_MSE.tiff), 80 × 80 × 80 × (Bx, By, Bz), in tesla;
- `mu_voxel`: their attenuation reconstruction (Structure_Recon_rot.tiff), per voxel;
- `voxel`: 23.8 mm / 128 = 0.186 mm;
- `measured`: their measured polarization matrices (Rock1_Stack_Cut.npy), 33 angles × 9 components × 80 × 80;
- `raden_lam`, `raden_w`: the wavelength profile of RADEN (Raden_Beam_Profile.npy).
