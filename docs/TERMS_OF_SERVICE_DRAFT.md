# ClearPath Nexus Enterprise Terms of Service

**Effective Date:** August 20, 2026
**Document Version:** 4.0.0-PROD
**Classification:** Legal & Operational Use Agreement

---

## 1. Acceptance and Operational Scope

By accessing, configuring, or using the **ClearPath Nexus Platform** (including the Web Command Dashboard, Mobile Applications, REST APIs, and associated services, collectively referred to as the "Service"), the operating organization ("Customer" or "Operator") agrees to these Terms of Service.

### 1.1 Non-Safety-Critical & Advisory Status
**CRITICAL OPERATIONAL NOTICE**: ClearPath Nexus is designed and provided strictly as an **Intermodal Decision Support & Corridor Planning System**. The Service **IS NOT**:
- A certified Railway Signalling or Electronic Interlocking System.
- An Automatic Train Protection (ATP), Cab Signalling, or Collision Avoidance System (e.g., Kavach, ETCS, TCAS).
- An automated train dispatch, locomotive braking, or track occupation authorization tool.
- A legally binding hazardous materials or over-dimensional consignment (ODC) movement permit.

### 1.2 Operator Due Diligence
All route feasibility scores, physical clearance calculations, Route Reliability Index (RRI) values, estimated times of arrival (ETA), and environmental risk advisories are heuristic estimates. Field dispatchers, loco pilots, and station masters must independently cross-verify all routing clearances against official Working Time Tables (WTT), Indian Railways Permanent Way (P-Way) manuals, Port Authority Berth Allocations, and authorized Operating Rules before authorizing train movements.

---

## 2. External Data Providers & Resilient Degradation

### 2.1 Provider Dependencies
The Service integrates meteorological, space-weather, maritime, and railway operational feeds from third-party APIs (including Open-Meteo, OpenWeather, NOAA SWPC, and connected enterprise logistics feeds).

### 2.2 Disclaimer of Provider Continuity
External feeds are subject to network latency, upstream provider maintenance, and upstream outages. When a provider feed is unreachable or stale, the Service explicitly enters an **Honest Degradation State** and flags data as unavailable. The absence of a severe weather alert or delay warning does not guarantee clear physical track conditions.

---

## 3. Account Security and Authorized Access

1. **Role-Based Access Control**: Access to planning and evaluation endpoints requires authenticated Operator or Administrator credentials.
2. **Credential Confidentiality**: Customers are solely responsible for safeguarding authentication cookies, API tokens, and secret keys.
3. **Automated Protection**: The platform enforces automated rate limiting and session expiration to protect against brute-force and credential-stuffing attacks.

---

## 4. Limitation of Liability

TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, IN NO EVENT SHALL THE DEVELOPERS, CONTRIBUTORS, OR AFFILIATES OF CLEARPATH NEXUS BE LIABLE FOR:
1. Any direct, indirect, incidental, punitive, or consequential damages arising from railway traffic disruptions, train delays, missed maritime vessel windows, or container demurrage penalties.
2. Physical damage to locomotives, rolling stock, track infrastructure, bridges, or cargo resulting from operator reliance on advisory clearance calculations.
3. Service interruptions caused by third-party meteorological or government data feed outages.

---

## 5. Acceptable Use and Compliance

The Customer agrees to use the Service in full compliance with:
- The Indian Railways Act, 1989 (and applicable regional railway regulations).
- Major Port Authorities Act, 2021.
- The Digital Personal Data Protection (DPDP) Act, 2023.
- Applicable national and international data privacy and cybersecurity regulations.

---

## 6. Governing Law & Dispute Resolution

These Terms shall be governed by and construed in accordance with the laws of the jurisdiction in which the enterprise deploying entity is established, without regard to conflict of law principles.
