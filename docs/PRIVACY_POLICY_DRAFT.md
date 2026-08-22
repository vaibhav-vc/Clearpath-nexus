# ClearPath Nexus Enterprise Privacy Policy

**Effective Date:** August 20, 2026
**Document Version:** 4.0.0-PROD
**Compliance Standards:** Digital Personal Data Protection (DPDP) Act 2023 / General Data Protection Regulation (GDPR)

---

## 1. Introduction

This Privacy Policy describes how the **ClearPath Nexus Platform** ("ClearPath Nexus", "we", "our", or "the Platform") collects, processes, stores, and protects personal and operational data generated through our Web Command Dashboard, Mobile Applications, and REST APIs.

---

## 2. Information Collected

We process the following categories of information strictly for operational and security purposes:

### 2.1 User & Operator Identity Data
- **Account Details**: Full name, operational email address, assigned role (`operator`, `admin`), hashed passwords (stored via adaptive `bcrypt` with salt), and account creation timestamps.
- **Session Metadata**: Cryptographic session identifiers, IP addresses, browser user-agents, and access token timestamps stored in memory or secure `httpOnly` SameSite cookies.

### 2.2 Geospatial & Operational Data
- **Train Location Input**: Station codes, latitude/longitude coordinates submitted for route snapping and delay simulation.
- **Cargo Specification Profiles**: Height (m), width (m), and weight (metric tonnes) attributes submitted for spatial clearance validation.
- **Historical Query Records**: Route evaluation queries recorded in the `generated_routes` table for audit trail and compliance verification.

---

## 3. Lawful Basis and Purpose of Processing

Data is processed under the following lawful bases:
1. **Contractual Necessity**: To provide freight route calculation, clearance evaluation, and multi-hazard risk assessment.
2. **Legitimate Interests**: To monitor API health, enforce rate limits, detect brute-force attacks, and improve route prediction models.
3. **Legal & Regulatory Compliance**: To retain necessary audit logs required under railway freight movement and port security regulations.

---

## 4. Third-Party Data Transmission & Subprocessors

ClearPath Nexus interacts with third-party data providers strictly on a need-to-know, anonymized coordinate basis:
- **Meteorological Services** (Open-Meteo, OpenWeather): Latitude and longitude bounding points sent to fetch weather forecasts. No personal user data is shared.
- **Space Weather Services** (NOAA SWPC): Public geomagnetic planetary Kp-index feeds consumed without transmitting any local user identifiers.
- **Maritime Port Community Systems**: Port Berth and Vessel identifiers transmitted to retrieve scheduled loading windows.

---

## 5. Data Retention & Purge Schedule

- **Authentication Sessions**: Revoked upon explicit logout or automated expiration (access tokens: 60 minutes; refresh tokens: 30 days max).
- **Route Query History**: Generated route records are subject to an automated retention schedule (default: 90 days) and purged via the database lifecycle maintenance subsystem (`purge_expired_routes`).
- **Security & Access Logs**: Anonymized structured JSON logs retained for 90 days for operational forensics.

---

## 6. Data Subject Rights & Contact

Authorized operators and users may request access, correction, or deletion of their account records by contacting their organization's designated System Administrator or Data Protection Officer (DPO).
