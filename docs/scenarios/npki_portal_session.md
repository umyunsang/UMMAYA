# Scenario: NPKI Portal Session (공인인증서 포털 세션)

**Why this is a scenario, not a mock**: The NPKI (공인인증서) portal session — the workflow by which a citizen obtains, renews, or revokes a certificate via a Korean Certificate Authority (CA) portal — is not publicly reproducible. The portal session protocol involves a proprietary browser plugin handshake (originally ActiveX-based, now transitioning to native messaging extension), a CA-specific session token format, and an OTP or biometric challenge-response sequence whose protocol is not disclosed in any public specification. The session establishment messages are transmitted over a CA-proprietary channel that is not described in any public RFC, 3GPP standard, or open SDK. Three major Korean CAs (YESSIGN, KOSCOM, NHN) each implement this session protocol differently and none publish a machine-readable specification.

> **Scope note**: The NPKI *cryptographic layer* (PKCS#7 signature, PKCS#12 bundle load/parse) IS mockable and lives at `docs/mock/npki_crypto`. This scenario covers only the portal session layer that sits above the crypto layer.

## Journey overview

A citizen uses KOSMOS to initiate a certificate-based authentication or signature that requires a valid, active NPKI certificate. If the citizen's certificate is expired or not yet issued, the journey includes a portal session step:

1. The citizen requests an operation requiring NPKI authentication (e.g., signing a form for a government submission).
2. KOSMOS attempts to load the citizen's PKCS#12 bundle from the device using the `npki_crypto` mock layer.
3. If the certificate is expired or absent, KOSMOS presents a human-readable message explaining the situation and, if the citizen consents, invokes the `delegate` primitive to hand off to the NPKI CA portal session.
4. The NPKI CA portal session proceeds externally: the citizen's browser opens the CA portal, installs or activates the native messaging extension, and completes the certificate issuance or renewal workflow (OTP challenge, biometric verification, and CA-signed certificate download).
5. The portal session ends with the CA portal writing a new PKCS#12 bundle to the citizen's device (the storage location and filename convention are CA-specific and not standardised).
6. KOSMOS is notified of the completion via a callback registered at handoff time (`delegate` return value includes a `session_complete` polling token).
7. KOSMOS polls the polling token (CA-specific endpoint) until `status: "complete"` or timeout (5 minutes), then re-attempts the PKCS#12 load using the `npki_crypto` mock layer.

## KOSMOS ↔ real system handoff point

The handoff occurs at step 3: when KOSMOS calls `delegate(tool_id="npki_portal_session", params={"ca_code": ..., "cert_type": ..., "citizen_id_hash": ...})`.

At this point:
- KOSMOS has determined that the citizen's certificate is expired, absent, or rejected by the target system.
- KOSMOS has the citizen's explicit consent to initiate a portal session (this is a consent-gated action).
- KOSMOS emits a `ToolCallAuditRecord` with `is_irreversible=False` (the session can be abandoned) before the handoff.
- The `delegate` call opens the CA portal URL in the citizen's default browser — KOSMOS does not render the portal UI.
- The portal session protocol (browser plugin handshake, OTP/biometric challenge, certificate download) is entirely managed by the CA portal and its native extension.
- KOSMOS receives a `{ session_token, poll_url, expires_at }` response from the `delegate` call; it uses `poll_url` to check session status.
- On successful certificate issuance: KOSMOS records `outcome: "portal_session_complete"` in the audit record and proceeds with the original operation.
- On timeout or failure: KOSMOS records the structured error (`{ ca_code, error_message, session_token }`) in the audit record and presents a human-readable failure message to the citizen.

## What KOSMOS does on our side

- Detects an expired or absent NPKI certificate during the `npki_crypto` load step (this detection is fully mockable).
- Obtains explicit citizen consent before initiating a portal session.
- Emits a `ToolCallAuditRecord` at handoff time.
- Polls the `poll_url` at 10-second intervals with a 5-minute total timeout through the portal-session handoff flow. This is not exposed as an active `subscribe` primitive.
- Records only the outcome (`complete` / `timeout` / `error`) and session token in the audit record — not any intermediate CA portal state.
- After a successful portal session, re-attempts the original operation from step 2.

## What KOSMOS deliberately does NOT do (harness discipline)

- KOSMOS does not implement the CA portal session protocol — the browser plugin handshake and OTP/biometric challenge are entirely opaque.
- KOSMOS does not access the CA portal's internal session state or inject into the browser session.
- KOSMOS does not store the citizen's PKCS#12 password or private key material — these are managed by the citizen's device and CA.
- KOSMOS does not support the legacy ActiveX plugin path — only the native messaging extension path is supported (modern browsers only).
- KOSMOS does not implement multi-CA session orchestration — the citizen must select a single CA before the handoff.

---

*Promoted to mock on <date>, tracked by #<issue>* — replace this line when a Korean CA publishes a public-facing sandbox or reference implementation of the portal session protocol.
