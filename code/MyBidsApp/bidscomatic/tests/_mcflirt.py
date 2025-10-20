MCFLIRT_STDOUT = (
    "Processed data will be saved as /tmp/derivatives/fsl/McFLIRT/sub-001/ses-01/run-01\n"
    "\n"
    "McFLIRT v 2.0 - FMRI motion correction\n"
    "\n"
    "Reading time series...\n"
    "first iteration - 8mm scaling, set tolerance\n"
    "Rescaling reference volume [354] to 8 mm pixels\n"
    "Registering volumes ... [355][356][357][358][359][360]\n"
    "second iteration - drop to 4mm scaling\n"
    "Rescaling reference volume [354] to 4 mm pixels\n"
    "Registering volumes ... [355][356][357][358][359][360]\n"
    "third iteration - 4mm scaling, eighth tolerance\n"
    "Registering volumes ... [355][356][357][358][359][360]\n"
    "Saving motion corrected time series...\n"
    "\n"
    "Final result: \n"
    "1.000000 0.000000 0.000000 0.000000 \n"
    "0.000000 1.000000 0.000000 0.000000 \n"
    "0.000000 0.000000 1.000000 0.000000 \n"
    "0.000000 0.000000 0.000000 1.000000 \n"
    "\n"
)

EXPECTED_IDENTITY_MATRIX = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]
