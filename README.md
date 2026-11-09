# X-IDS 2.0 — Real-Time Explainable Intrusion Detection System

X-IDS 2.0 upgrades the supplied Django IDS project into a local-first security monitoring application. It retains the supplied CIC-IDS2017 dataset, preprocessing artifacts, LSTM/TCN weights, and the original dataset research workflow while adding a React dashboard, Django REST API, WebSocket event feed, live packet capture, PCAP analysis, threat enrichment, network topology, PDF reporting, email notifications, and guarded firewall response.

> **Research / validation notice:** The supplied models were trained on CIC-IDS2017 flow features. The live/PCAP adapter aggregates packet headers into the same feature names, but some CICFlowMeter-derived values cannot be reconstructed from the limited packet metadata and are zero-filled. Live predictions are therefore experimental until compared with CICFlowMeter/NFStream exports and validated on representative traffic. The included training data/model labels are binary (`Attack` and `Normal`), so the supplied models do not identify a specific attack family such as DDoS or brute force. Do not use the dashboard as the sole security control.

## Included features

- **Live network monitoring:** Scapy packet capture from a selected network interface; packet/byte/protocol counters; bidirectional TCP/UDP flow aggregation; live event delivery over WebSockets.
- **AI attack detection:** Lazily loads the original saved LSTM and TCN weights; averages available model probabilities; records the model-wise prediction and confidence. A flow is marked `UNSCORABLE` if the saved artifacts or model dependencies cannot be loaded.
- **Anomaly detection / unknown-pattern triage:** An Isolation Forest is fitted on the Normal CIC-IDS2017 baseline and flags outlier flows independently of the binary classifier. This is an anomaly signal, not proof of a zero-day attack.
- **Risk trend and network health:** Dashboard compares current and previous 24-hour alert counts, and the live sensor reports packet rate, byte throughput, protocol counts and capture uptime.
- **User roles:** Django session login, administrator/analyst roles, and an administrator-only user-management screen. Analysts can view/investigate/acknowledge; firewall and policy actions are administrator-only.
- **Explainable AI:** Per-event LIME explanation using the same model ensemble and SHAP `GradientExplainer` attribution for the loaded LSTM.
- **Security dashboard:** Traffic/activity charts, protocol mix, event queue, status of the capture agent and model artifacts.
- **Alert management:** Severity, search, acknowledgement, event history, and analyst actions.
- **PCAP analysis:** Upload `.pcap`, `.pcapng`, or `.cap` files; aggregate flows and run model inference.
- **IP reputation:** Optional AbuseIPDB integration (API key required).
- **GeoIP:** Optional MaxMind GeoLite2 City database integration (`.mmdb` file required).
- **Network topology:** Passive graph of observed source/destination endpoints and flows.
- **Reports:** Download a PDF summary.
- **Email alerts:** Optional SMTP notifications; credentials are configured in `.env`.
- **Response:** Manual firewall block/unblock; optional automatic blocking with a confidence threshold. Automatic blocking is **off by default**. Only public/routable IP addresses are accepted; private/loopback addresses are refused. Firewall changes require Administrator/root privileges.
- **Legacy research workflow:** Original CSV training/evaluation/explainability pages remain at `/research/`.

## Technology

- Frontend: React 18, Vite, Tailwind CSS, Recharts, Lucide, React Flow
- Backend: Django 5.2 LTS, Django REST Framework, Django Channels / Daphne
- Capture/PCAP: Scapy
- ML/XAI: TensorFlow 2.15, LSTM, keras-tcn, SHAP, LIME, scikit-learn
- Data: SQLite by default; optional PostgreSQL 16 via Docker Compose
- Intelligence/reporting: requests, geoip2, ReportLab, SMTP

## Windows quick start (recommended)

### 1. Prerequisites

Install:

1. **Python 3.11.x (64-bit)** — TensorFlow 2.15 is pinned in this project; Python 3.11 is the required/recommended runtime for these ML wheels.
2. **Node.js 20+ (LTS recommended)** — npm is included with Node.js.
3. **Npcap** — required for live packet capture on Windows. Install from the official Npcap site and enable WinPcap API-compatible mode if offered.
4. **Wireshark is optional** — useful for validating captures, but X-IDS uses Scapy for PCAP reading.

### 2. Extract and set up

Extract the project ZIP into a folder such as `C:\Projects\X-IDS-2.0`.

Double-click `setup_windows.bat` or run these commands from Command Prompt in the project folder:

```bat
py -3.11 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
cd frontend
npm install
cd ..
python manage.py createsuperuser
```

Create the first administrator account when prompted. You will use it to sign in to the React dashboard and create Analyst or Administrator accounts from **Users & roles**.

TensorFlow is a large dependency; its installation can take several minutes and needs an internet connection. Keep Python 3.11 selected for this environment.

### 3. Start the application

Double-click `start_xids.bat`, or use two terminal windows.

**Terminal 1 — backend** (use Administrator for live capture / firewall actions):

```bat
venv\Scripts\activate
python manage.py runserver 127.0.0.1:8000
```

**Terminal 2 — frontend:**

```bat
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173/** and sign in with the superuser account created above.

Backend health check: **http://127.0.0.1:8000/api/health/**

### 4. Start live capture

1. Start the backend from an Administrator PowerShell/Command Prompt window.
2. Open X-IDS → **Live monitoring**.
3. Choose your active Wi-Fi/Ethernet interface.
4. Click **Start capture**.
5. Generate normal activity on the computer (browse a few sites, use DNS, make a local request). Wait for flows to become idle and flush into the dashboard.
6. Review **Threat alerts** and select an event in **Explainable AI** to generate SHAP/LIME explanations.

Capture is passive. The program only sees packets that the selected interface and operating system make visible to it. A laptop normally cannot observe every other device's unicast traffic on a switched LAN/Wi-Fi network.

### 5. Whole-LAN monitoring

To monitor multiple devices, place the sensor at an authorized visibility point: a router/gateway you administer, a managed switch mirror/SPAN port, or a network TAP. Connect the sensor to that feed and select the corresponding adapter. Do not capture networks without permission.

## Optional configuration

Copy `.env.example` to `.env` and edit it. Keep `.env` private; never commit API keys or SMTP passwords.

### PostgreSQL (optional)

SQLite is the zero-configuration default. To use PostgreSQL:

```bat
docker compose up -d postgres
```

Then add this to `.env`:

```env
DATABASE_URL=postgresql://xids:xids_local_dev@127.0.0.1:5432/xids
```

Run `python manage.py migrate` again. Change the example password before exposing the database beyond your machine.

### AbuseIPDB

Create an API key with AbuseIPDB, then set:

```env
ABUSEIPDB_API_KEY=your_key_here
```

Restart Django. The IP reputation page will then show report counts and abuse-confidence scores for public IPs. Private IPs are deliberately not sent to the provider.

### GeoIP

Download a MaxMind GeoLite2 City `.mmdb` database under the terms of its provider, then set its absolute path:

```env
GEOIP_DB_PATH=C:/GeoIP/GeoLite2-City.mmdb
```

Restart Django. GeoIP is approximate and should not be treated as a precise physical location.

### SMTP email alerts

Set SMTP values in `.env`, for example:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=you@example.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=you@example.com
XIDS_ALERT_RECIPIENT=security@example.com
XIDS_EMAIL_ENABLED=true
```

Restart Django, then enable **Email alerts** under Configuration. Use an app password where your provider requires one. The Reports & response page has a test-email control.

## Response safety

- Automatic blocking starts disabled. Enable it only after validating model behavior in your environment.
- Manual and automatic actions are limited to public IPs and respect the configured `XIDS_IP_WHITELIST`.
- Firewall actions require administrator/root permissions and can interrupt connectivity. Keep console access available; do not block your router, gateway, DNS resolver, remote management host, or any address you rely on.
- Treat model predictions as investigation signals. Confirm with packet evidence and an independent security tool before responding to incidents.

## Legacy dataset workflow

The original uploaded project has been preserved under `/research/`:

- `/research/` overview
- `/research/upload/` dataset upload
- `/research/preprocess/`
- `/research/split/`
- `/research/lstm/`
- `/research/tcn/`
- `/research/compare/`
- `/research/explain/`
- `/research/predict/`

The original trained weights and preprocessing artifacts remain in `model/`; the source CIC-IDS2017 data remains in `dataset/`.

## API overview

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health/` | GET | Backend health |
| `/api/dashboard/summary/` | GET | Dashboard statistics and model status |
| `/api/events/` | GET | Recent flows / alerts |
| `/api/events/<id>/explain/` | POST | Generate SHAP + LIME explanation |
| `/api/events/<id>/acknowledge/` | POST | Acknowledge an alert |
| `/api/monitor/interfaces/` | GET | List capture adapters |
| `/api/monitor/start/` | POST | Start packet capture |
| `/api/monitor/stop/` | POST | Stop packet capture |
| `/api/pcap/analyze/` | POST | Analyze a PCAP upload |
| `/api/ip/reputation/` | POST | AbuseIPDB lookup |
| `/api/ip/geo/?ip=<ip>` | GET | GeoIP lookup |
| `/api/topology/` | GET | Observed network graph |
| `/api/response/block/` | POST | Add firewall block rules |
| `/api/response/unblock/` | POST | Remove X-IDS firewall rules |
| `/api/reports/pdf/` | GET | Download PDF report |
| `/api/settings/` | GET/POST | Local response settings |

WebSocket live feed: `/ws/events/`.

## Known limitations / next validation work

1. **Feature extraction parity:** The supplied CIC-IDS2017 models were trained on dataset flow features. The included Scapy flow aggregator computes observable packet statistics and zero-fills unavailable fields. Before operational use, validate or replace this adapter with a CICFlowMeter/NFStream extractor producing the exact feature columns and units used in training.
2. **Binary labels:** The included artifact `labels.pkl` contains `Attack` and `Normal` only. This version does not name attack families or claim to distinguish DDoS from brute force.
3. **Model metrics:** Metrics from the original training/evaluation interface are kept in the legacy research pages; live inference should be independently tested with labelled traffic and false-positive/false-negative rates.
4. **Sensor scope:** Entire-LAN coverage depends on network configuration and capture placement.
5. **External data:** IP reputation, GeoIP and email depend on optional provider credentials/database/network access.
6. **Local-first prototype:** The project is intended for a trusted local lab. It does not include internet-facing production authentication, multi-user tenancy, TLS termination, or a hardened deployment configuration.

## Troubleshooting

- `Npcap not found` / permission denied: install Npcap, restart Windows, run the backend as Administrator, and select the active adapter.
- Model status says offline: confirm Python 3.11, install all requirements, and verify `model/lstm_weights.hdf5`, `model/tcn_weights.hdf5`, `model/features.pkl`, `model/labels.pkl`, and `model/scaler.pkl` exist. Read model errors in the dashboard summary response.
- Frontend API error: make sure Django is running at `127.0.0.1:8000` and Vite is running at `127.0.0.1:5173`.
- `npm` not found: install Node.js 20+ and reopen the terminal.
- WebSocket disconnected: keep the Django ASGI/Daphne server running and check the backend terminal for errors.
- Empty topology/charts: start capture and wait for idle flows to be finalized, or upload a PCAP file.
