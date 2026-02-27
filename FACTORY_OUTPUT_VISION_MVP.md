# Factory Output Vision MVP

## 1) Full Project Structure

```text
.
├── backend
│   ├── data/
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── config
│   └── config.json
├── dashboard
│   └── app.py
├── docker
│   ├── Dockerfile.backend
│   ├── Dockerfile.dashboard
│   └── Dockerfile.edge
├── edge
│   ├── evidence/
│   ├── counter.py
│   └── main.py
├── scripts
│   ├── capture_empty_reference.py
│   └── select_roi.py
├── docker-compose.yml
└── requirements.txt
```

## 2) Source Files

All source files are included in this repository under the paths listed above.

## 3) Deployment Instructions

### Local Development

1. Copy and edit `config/config.json`:
   - Put real RTSP URLs.
   - Set ROI coordinates.
   - Set `empty_reference_path`.
2. Set environment:

```bash
export API_USER=admin
export API_PASSWORD='strong-password'
export CAMERA_IDS='cam1,cam2'
```

3. Start stack:

```bash
docker compose up -d --build
```

4. Open:
- Backend API: `http://localhost:8000/docs`
- Dashboard: `http://localhost:8501`

### Deploy to DigitalOcean (Droplet)

1. Create a CPU droplet (`Basic`, 2 vCPU, 4GB RAM, Ubuntu 22.04).
2. Install Docker + Compose plugin.
3. Clone repo and copy `config/config.json`.
4. Open ports: `22`, `8000` (optional), `8501`.
5. Run:

```bash
docker compose up -d --build
```

6. Add reverse proxy/TLS (Caddy or Nginx) for dashboard/API.

### Deploy to AWS Lightsail

1. Create Linux instance (2 vCPU / 4GB RAM).
2. Open networking ports `22`, `80`, `443`, and optionally `8501`.
3. Install Docker and compose plugin.
4. Clone repository and configure environment values.
5. Launch:

```bash
docker compose up -d --build
```

6. Put dashboard/API behind HTTPS reverse proxy.

## Reolink RTSP Setup

1. Reolink App/Web UI → **Settings** → **Network** → **Advanced** → enable **RTSP**.
2. Ensure camera has static LAN IP.
3. Typical stream URL format:

```text
rtsp://<user>:<password>@<camera-ip>:554/h264Preview_01_main
```

## Validate RTSP with VLC

1. Open VLC.
2. `Media` → `Open Network Stream`.
3. Paste RTSP URL.
4. Confirm live stream and acceptable latency.

## ROI Selection

```bash
python scripts/select_roi.py --source 'rtsp://user:pass@192.168.1.10:554/h264Preview_01_main' --output config/roi.txt
```

Copy ROI array into `config/config.json` camera entry.

## Capture Empty Reference Frame

Run while DONE ZONE is empty:

```bash
python scripts/capture_empty_reference.py --rtsp 'rtsp://user:pass@192.168.1.10:554/h264Preview_01_main' --roi '[120,180,500,300]' --output config/empty_cam1.jpg
```

## 4) Scaling Instructions (1 → 6 cameras)

1. Add additional camera objects in `config/config.json` under `cameras`.
2. For each camera configure unique:
   - `camera_id`
   - `rtsp_url`
   - `roi`
   - `mode`
   - `empty_reference_path`
3. Keep `sample_seconds` at 10–15s.
4. If CPU climbs above ~75%:
   - Increase `sample_seconds` to 20s.
   - Reduce `resize_width` (e.g. 640).
   - Enable `adaptive_sampling`.
5. Set `CAMERA_IDS` env var for dashboard selector.

## 5) Cost Estimation (<$50/month target)

### DigitalOcean
- 2 vCPU / 4GB droplet: ~$24/month
- 80GB disk: included
- Snapshot/backups optional: +$5 to +$10
- Total typical: **$24–$34/month**

### AWS Lightsail
- 2 vCPU / 4GB plan: ~$20/month
- Data transfer included allowance sufficient for sparse frame uploads
- Total typical: **$20–$30/month**

### Why this stays low-cost
- No paid AI API.
- No GPU.
- Frame pull every 10–15 seconds only.
- Event-only evidence uploads.
- SQLite default.

## 6) Known Failure Modes + Mitigations

1. **RTSP disconnects / packet loss**
   - Mitigation: reconnect retries and release/reopen capture in edge service.
2. **Lighting variation causes false positives**
   - Mitigation: blur + threshold + morphology; tune threshold and empty reference refresh.
3. **Transient object noise causing overcount**
   - Mitigation: persistence-based state transitions (`persistence_frames`).
4. **Bin reset or manual clearing**
   - Mitigation: reset detection logic with threshold.
5. **Low confidence estimates**
   - Mitigation: confidence score output and event evidence upload for operator review.
6. **CPU saturation with multiple cameras**
   - Mitigation: resize frames, adaptive sampling, longer intervals.
7. **Storage growth from evidence images**
   - Mitigation: upload only on increment/downtime/low-confidence; periodically prune old evidence.
