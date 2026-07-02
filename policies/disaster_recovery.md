# Disaster Recovery and Business Continuity Policy

## Overview

TTB Bank maintains a Disaster Recovery (DR) and Business Continuity Plan (BCP) to ensure that critical banking services can be restored promptly following a disruption. This document summarises the key targets and procedures for IT and operations staff.

## Recovery Objectives

### Recovery Time Objective (RTO)

| System Tier | RTO |
|---|---|
| Tier 1 (Core Banking, Payments) | **4 hours** |
| Tier 2 (Internet Banking, Mobile App) | 8 hours |
| Tier 3 (Internal tools, Reporting) | 24 hours |

### Recovery Point Objective (RPO)

| System Tier | RPO |
|---|---|
| Tier 1 (Core Banking, Payments) | **1 hour** (maximum data loss) |
| Tier 2 (Internet Banking, Mobile App) | 4 hours |
| Tier 3 (Internal tools, Reporting) | 24 hours |

## Architecture

- **Core banking systems** run on a **hot standby** configuration with real-time data replication to the secondary data centre.
- Tier 2 systems use warm standby (data replicated every 4 hours).
- Tier 3 systems use cold standby (daily backups, manual restore).

## DR Testing

**Annual DR tests** are conducted for all Tier 1 systems. Tests include:

- Full failover to secondary data centre
- Verification of all critical business processes
- RTO/RPO measurement against targets
- Post-test report submitted to the Board Risk Committee

Tier 2 and Tier 3 systems are tested every 18 months.

## Incident Declaration

A DR event is declared by the CTO or a designated deputy. Upon declaration:

1. Crisis Management Team convenes within 30 minutes
2. Affected business units activate BCP procedures
3. IT initiates failover procedures per the DR runbook
4. Communications to staff and customers managed by Corporate Communications

## Data Backup

- Tier 1 data is replicated in real-time to the secondary site
- Daily full backups are retained for 90 days
- Monthly backups are retained for 7 years (regulatory requirement)
- Backup integrity is verified monthly via restore tests

## Contact

For DR-related queries, contact the IT Infrastructure team at dr@ttb.co.th.
