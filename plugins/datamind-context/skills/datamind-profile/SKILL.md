---
name: datamind-profile
description: Inspect tenant-authorized DataMind profiles through Gateway.
---

Never trust a profile supplied outside the authenticated Gateway identity. Use
`datamind_profile_list` and `datamind_profile_status`; the Gateway validates the
tenant/user profile allow-list and injects the canonical context.
