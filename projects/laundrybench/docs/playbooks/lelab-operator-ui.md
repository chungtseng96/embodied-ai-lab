# LeLab operator UI

**Status:** recommended operator surface for the LeRobot SO-101 bring-up;
physical motion remains supervised and operator-validated.

[LeLab](https://github.com/huggingface/leLab) is Hugging Face's web UI for
LeRobot. It supplies the browser workflow that Phosphobot does not share with
our canonical LeRobot calibration and evaluation path: guided calibration,
leader/follower teleoperation, live joint streaming, camera previews and
rotation, recording, replay, inference, and dataset browsing.

LaundryBench remains responsible for the experiment/evaluation contracts and
review UI. LeLab is the operator front door for the hardware workflow; it does
not turn a connected arm or a preview into physical task evidence.

## Intel macOS compatibility

The current LeLab `main` branch pins a newer LeRobot/Torch combination that
does not resolve to an Intel-macOS Torch wheel. Use the LeLab revision pinned
to the LeRobot 0.6.1 API used by this checkout:

```text
444638b083ad0262c57ec5e15f226e0916de5f10
```

Keep the LeLab web environment separate from the validated LeRobot environment.
The compatibility launcher uses the selected LeRobot environment through
`PYTHONPATH`; it does not replace its LeRobot, Torch, camera, or calibration
packages.

Create the environment once:

```bash
uv venv .venv-lelab --python 3.12
uv pip install --python .venv-lelab/bin/python \
  'fastapi[standard]>=0.115.12' 'websockets>=15.0.1' \
  'uvicorn>=0.24.0' 'psutil>=5.9.0'
uv pip install --python .venv-lelab/bin/python --no-deps \
  'LeLab @ git+https://github.com/huggingface/leLab.git@444638b083ad0262c57ec5e15f226e0916de5f10'
```

Launch it with the already validated LeRobot Python:

```bash
python3 projects/laundrybench/scripts/run_lelab.py \
  --lelab-python .venv-lelab/bin/python \
  --lerobot-python /absolute/path/to/laundrybench-lerobot-e2e/bin/python
```

Open <http://127.0.0.1:8000>. The equivalent Make target is:

```bash
make lelab-ui \
  LEROBOT_PYTHON=/absolute/path/to/laundrybench-lerobot-e2e/bin/python
```

The launcher refuses a selected LeRobot version other than 0.6.1. The
LeRobot calibration files remain the source of truth:

```text
~/.cache/huggingface/lerobot/calibration/robots/so_follower/
~/.cache/huggingface/lerobot/calibration/teleoperators/so_leader/
```

Before starting teleoperation, confirm the UI shows the exact leader and
follower ports and calibration IDs, keep both arms supported, keep the physical
stop accessible, and start with small leader motions. Stop immediately if the
follower direction, tracking, or serial connection is unexpected.

## Camera policy

LeLab enumerates macOS camera names and supports software rotation at 0°, 90°,
180°, or 270°. Select the mounted arm camera for the policy/front stream and
the C920 for the third-person stream; do not select the iPhone. The selected
rotation must match the training/rollout contract for new data.

The current host's no-motion camera inventory is:

- arm-mounted `icspring camera`: OpenCV index 0, device ID `0x1443100029930858`;
- C920 third-person camera: index 1, device ID `0x14433000046d08e5`;
- FaceTime HD: index 2;
- iPhone and iPhone Desk View: indexes 3 and 4.

A LeLab preview is not proof that the LaundryBench camera stream was captured
by the selected LeRobot recording command. Keep the iPhone devices excluded
from the LeLab profile.
