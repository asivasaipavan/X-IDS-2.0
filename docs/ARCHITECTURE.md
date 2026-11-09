# X-IDS 2.0 architecture notes

```text
Laptop / LAN mirror / PCAP
        |
        v
Scapy capture + PCAP reader
        |
        v
Bidirectional flow aggregator
        |
        v
CIC feature-name adapter (feature values not observable from packet headers are zero-filled)
        |
        v
Saved model artifacts -> LSTM + TCN -> mean probability ensemble
        |                                   |
        |                                   +--> SHAP GradientExplainer (LSTM) + LIME (ensemble)
        v
NetworkEvent database -> Django REST API -> React dashboard
        |                       |
        |                       +--> WebSocket live event broadcast
        +--> Alert/email/PDF/GeoIP/IP reputation/topology
        +--> Optional guarded firewall response
```

## Capture lifecycle

`MonitorManager` owns a single daemon capture thread in the Django process. Scapy reads packets from one interface and the `FlowAggregator` groups TCP/UDP packets by a bidirectional 5-tuple. A flow is finalized after an idle timeout and sent through the inference engine. `process_flow()` persists each event and broadcasts it through the Channels in-memory layer. Run a single Django process for the local monitor; the in-memory capture manager and channel layer are not a multi-worker distributed capture service.

## Security boundaries

- The app binds to loopback in the documented quickstart; do not expose it on an untrusted network.
- Firewall response is disabled by default and rejects non-global IP addresses.
- External enrichment is performed only when an operator submits an IP and configures provider credentials.
- Packet payloads are not persisted by the event pipeline; it stores flow metadata and derived features.
