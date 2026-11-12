# Live operator telemetry

LaundryBench includes a read-only `/operator` view for watching the follower
SO-101 pose while LeLab owns teleoperation and camera control. This view is a
bring-up aid, not a second robot-control implementation.

## Start the surfaces

1. Start LeLab using the [LeLab operator playbook](lelab-operator-ui.md).
2. Start or build the LaundryBench frontend:

   ```bash
   npm ci --prefix projects/laundrybench/frontend
   npm run build --prefix projects/laundrybench/frontend
   make web
   ```

3. Open `http://127.0.0.1:8765/operator`.

For frontend development, run `make web-demo` once and then:

```bash
npm run dev --prefix projects/laundrybench/frontend
```

Open `http://127.0.0.1:5173/operator`. The dashboard connects to LeLab at
`http://127.0.0.1:8000` by default. Override it with the `lelab` query
parameter when using another loopback port.

## What the view means

- `LeLab connected` means the WebSocket endpoint is reachable.
- `Teleoperation active` comes from LeLab's status endpoint.
- `LIVE` means a joint frame arrived within the last second.
- The six cards show LeLab's follower joint positions in radians. Missing
  values remain visible as `—`.
- The page is read-only and sends no movement, calibration, recording, or
  policy commands.

The dashboard consumes LeLab's existing `/ws/joint-data` stream. It does not
claim leader/follower synchronization error because the current LeLab stream
publishes follower pose only; that comparison can be added after the backend
exposes leader telemetry with an explicit contract.
