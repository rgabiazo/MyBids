# ICA-AROMA
ICA-AROMA (i.e. ‘ICA-based Automatic Removal Of Motion Artifacts’) concerns a data-driven method to identify and remove motion-related independent components from fMRI data. To that end it exploits a small, but robust set of theoretically motivated features, preventing the need for classifier re-training and therefore providing direct and easy applicability. This package requires an installation of Python and FSL. Read the provided 'Manual.pdf' for a description on how to run ICA-AROMA. Make sure to first install all required python packages: `python -m pip install -r requirements.txt`.


The provided Dockerfile builds from
`vnmd/fsl_6.0.7.14` and installs Python 2.7 together
with the packages listed in `requirements.txt`.  Build the image with:

```bash
docker build -t ica_aroma code/ICA-AROMA-master
```

Run ICA‑AROMA inside the container by passing the desired arguments to
`ICA_AROMA.py`:

```bash
docker run --rm ica_aroma python2 ICA_AROMA.py -in <input> -out <output> ...
```

**! NOTE**: Previous versions of the ICA-AROMA scripts (v0.1-beta & v0.2-beta) contained a crucial mistake at the denoising stage of the method. Unfortunately this means that the output of these scripts is incorrect! The issue is solved in version v0.3-beta onwards. It concerns the Python scripts uploaded before the 27th of April 2015.

**Log report (applied changes from v0.2-beta to v0.3-beta):**

1) Correct for incorrect definition of the string of indices of the components to be removed by *fsl_regfilt*:

	changed   denIdxStr = np.char.mod('%i',denIdx)
	to        denIdxStr = np.char.mod('%i',(denIdx+1))
2) Now take the maximum of the 'absolute' value of the correlation between the component time-course and set of realignment parameters: 

	changed   maxTC[i,:] = corMatrix.max(axis=1)
	to        corMatrixAbs = np.abs(corMatrix)
              maxTC[i,:] = corMatrixAbs.max(axis=1)
3) Correct for the fact that the defined frequency-range, used for the high-frequency content feature, in few cases did not include the final Nyquist frequency due to limited numerical precision:

	changed   step = Ny / FT.shape[0]
	          f = np.arange(step,Ny,step)
	to        f = Ny*(np.array(range(1,FT.shape[0]+1)))/(FT.shape[0])
