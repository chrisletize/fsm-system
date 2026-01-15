# FSM System - Hardware Infrastructure Plan
*Last Updated: 2026-01-14*
*Status: Planning Phase - To Be Implemented After Software Proves Viable*

## Executive Summary

**Purpose:** Production-grade hardware for custom FSM system serving 4 companies, ~30 users, 250 jobs/day peak.

**Budget:** ~$3,900 total (server + router + spares + networking)

**Power:** ~123W average draw = $11/month electricity (~$128/year)

**ROI:** System pays for itself in 2.1 months via ServiceFusion savings alone.

---

## Design Philosophy

### Core Requirements
1. **Redundancy:** Mirror all storage, dual network paths, UPS protection
2. **Remote Management:** IPMI for lights-out management
3. **Reliability:** Business-critical uptime, graceful degradation
4. **Performance:** Snappy web interface, instant response times
5. **Efficiency:** Low power consumption vs old enterprise servers
6. **Simplicity:** Not overbuilt for scale, easy to maintain

### Right-Sizing
- **30 users** (5 office, 25 mobile)
- **250 jobs/day** peak season
- **LOW** concurrent load (5-10 users simultaneously)
- Web app + PostgreSQL database
- Internal network traffic only

**Result:** This is a LIGHT workload. Focus on reliability over raw power.

---

## Main Application Server

### Component Selection

**CPU: AMD Ryzen 9 7900 (non-X)** - $430
- 12 cores / 24 threads
- 65W TDP (efficient, quiet)
- 28 PCIe 5.0 lanes
- Excellent single-thread performance = snappy UI
- **Why not EPYC:** Overkill for scale, lower clocks = slower web response

**Motherboard: ASRock Rack X570D4I-2T** - $500
- **Built-in IPMI/BMC** (remote management, KVM over IP)
- Dual 10GbE SFP+ (for future flexibility)
- ECC memory support
- Mini-ITX form factor (rackmount friendly)
- Industrial-grade components
- **Decision:** Worth $300 premium for built-in IPMI vs consumer board

**RAM: 64GB DDR4 ECC (2x32GB)** - $240
- Kingston or Crucial server-grade
- ECC for data integrity (business-critical data)
- 64GB provides headroom for growth

**Boot Storage: 2x 500GB Samsung 990 Pro (RAID1)** - $120
- Mirrored NVMe for OS/applications
- If one drive fails, system keeps running
- **Critical redundancy point #1**

**Data Storage: 2x 2TB Samsung 990 Pro (RAID1)** - $360
- Mirrored NVMe for PostgreSQL database
- High IOPS for snappy queries
- Redundant for safety

**Backup Storage: 2x 4TB WD Red (RAID1)** - $180
- Local backup mirror (nightly automated)
- Part of 3-2-1 backup strategy
- Warm backups for quick recovery

**Power Supply: Corsair RM750x 80+ Gold** - $120
- Single quality PSU + UPS (more practical than dual PSU)
- 10-year warranty
- 750W provides 3x headroom over peak load

**Case: 2U Rackmount (Supermicro SC216 or similar)** - $300
- Hot-swap drive bays
- Standard 19" rack mount
- Good airflow for 24/7 operation

**UPS: CyberPower PR1500LCDRTXL2U** - $550
- 2U rackmount form factor
- 1500VA/1500W capacity
- Pure sine wave (protects components)
- ~15-20 min runtime at typical load
- Network management card
- **Critical redundancy point #2**

**Network: Built into motherboard**
- Use onboard 2.5GbE + add PCIe 2.5GbE card for LACP bonding
- Dual path redundancy
- **Decision:** Skip 10GbE complexity, 2.5GbE is plenty for this load

**Total Main Server: $2,800**

---

## OPNsense Router/Firewall

### Component Selection

**CPU: AMD Ryzen 5 7600** - $220
- 6 cores / 12 threads
- 65W TDP
- More than sufficient for routing/firewall duties

**Motherboard: ASRock B650M-HDV/M.2** - $110
- Dual M.2 slots (for RAID1)
- 2.5GbE built-in
- Micro-ATX form factor

**RAM: 32GB DDR5 (2x16GB)** - $100
- Non-ECC acceptable for router
- Plenty for OPNsense + packages

**Boot Storage: 2x 256GB NVMe (RAID1)** - $60
- Mirrored for reliability
- OPNsense config redundancy

**Network Card: Intel I350-T4 (Quad 1GbE)** - $80
- 4x 1GbE ports for LAN zones
- Intel NICs = excellent OPNsense compatibility
- Plus motherboard 2.5GbE for WAN

**Power Supply: Corsair RM550x 80+ Gold** - $90
- Quality PSU sufficient for router load
- Single PSU + UPS acceptable for this component

**Case: 1U Rackmount (short depth)** - $150
- Compact, standard 19" mount

**Total OPNsense Router: $810**

---

## Spare Parts & Emergency Kit

**Purpose:** Enable rapid repair during hardware failure

**Spare PSU (Corsair RM750x)** - $120
- Swap in 30 minutes if main PSU fails
- Most common failure point

**Spare Boot NVMe (500GB Samsung 990 Pro)** - $60
- Quick replacement if boot drive fails

**Spare RAM Module (32GB DDR4 ECC)** - $120
- Replace failed stick immediately

**Total Spare Parts: $300**

**Recovery Time Objective (RTO) with spares:**
- PSU failure: 30 min
- Boot drive failure: 45 min
- RAM failure: 15 min
- Complete server failure: 2-3 hours (rebuild from backup)

---

## Networking Infrastructure

**2x Managed 2.5GbE Switches (8-port)** - $200
- LACP bonding support
- VLAN capability for network segmentation
- Managed for troubleshooting

**Cat6 Cabling** - $50
- Quality cables for 2.5GbE

**Fiber Patch Cables** - $40
- For dual internet connection failover

**Total Networking: $290**

---

## Rack & Organization

**12U Wall-Mount Rack** - $200
- Sufficient space for:
  - 2U main server
  - 1U OPNsense router
  - 2U UPS
  - 1U switch shelf
  - 6U available for expansion

**Cable Management Kit** - $50
- Keeps rack organized and professional

**1U Shelf for Switches** - $30
- Mounts 2x 2.5GbE switches

**Total Rack & Organization: $280**

---

## Complete System Cost Breakdown

### Minimum Viable
- Main Server: $2,800
- OPNsense Router: $810
- **Subtotal: $3,610**

### Recommended Production Setup
- Minimum Viable: $3,610
- Spare Parts Kit: $300
- Networking: $290
- Rack & Organization: $280
- **Total: $4,480**

### Optional Additions
- Additional UPS for network gear: $150
- 10GbE upgrade path (if needed later): $200
- KVM over IP (if IPMI insufficient): $300

---

## Power Analysis

### Power Consumption
**Main Server:**
- Idle: 64W
- Typical: 102W
- Peak: 133W

**OPNsense Router:**
- Idle: 47W
- Typical: 71W
- Peak: 96W

**Combined System:**
- Average draw: 123W
- Monthly: 88.56 kWh
- **Cost: $10.63/month** ($0.12/kWh)
- **Annual: $128/year**

### Comparison to Previous Setup
**Old: 3x Dell Enterprise Servers**
- Combined draw: ~840W
- Monthly cost: $72/month
- Annual: $870/year

**Savings: $742/year in electricity**

---

## Backup Strategy (3-2-1 Rule)

### 3 Copies of Data
1. **Production:** Live data on mirrored NVMe
2. **Local Backup:** Nightly to mirrored HDD in same server
3. **Cloud Backup:** Daily to Backblaze B2 (offsite)

### 2 Different Media Types
- NVMe (production + working set)
- HDD (local backup, different failure mode)
- Cloud object storage (offsite)

### 1 Offsite Copy
- Backblaze B2: ~$6/TB/month
- Estimated data: 100GB initially, 500GB after 2 years
- Cost: $3-5/month

**Total Backup Cost: ~$72/year**

### Backup Schedule
- **Continuous:** PostgreSQL WAL archiving (point-in-time recovery)
- **Hourly:** Database snapshots
- **Nightly:** Full system backup to local HDD + cloud
- **Weekly:** Full system image backup
- **Monthly:** Archive snapshot (retained 1 year)

### Recovery Scenarios
- **Database corruption:** Restore from hourly snapshot (<5 min)
- **Drive failure:** RAID1 continues operating (0 downtime)
- **Complete server failure:** Rebuild from backup (2-3 hours)
- **Office fire/disaster:** Restore from cloud to new hardware (4-8 hours)

---

## Network Redundancy

### Dual Internet Connections
**Primary: Business Fiber**
- Static IP
- 500 Mbps+ (adequate for load)
- SLA guarantee
- Cost: ~$150-250/month

**Backup: 5G Cellular**
- Different infrastructure (true redundancy)
- 100+ Mbps typical
- Automatic failover via OPNsense
- Cost: ~$75-150/month

**Failover Logic:**
- OPNsense monitors both connections
- Primary fails → switches to 5G (30 sec)
- Primary returns → switches back automatically
- Users experience brief interruption, system stays online

### Internal Network Redundancy
**LACP Bonding:**
- Main server: Dual 2.5GbE bonded
- OPNsense: Dual 2.5GbE bonded
- Automatic failover if one path fails
- Bandwidth aggregation (can use both simultaneously)

---

## Remote Management

### IPMI/BMC Capabilities
**Built into ASRock Rack motherboard:**
- Full KVM over IP (keyboard, video, mouse)
- Remote power control (power on/off/cycle)
- BIOS access (configure without being onsite)
- Hardware monitoring (temps, fans, voltages)
- Serial over LAN console access
- Virtual media mounting (install OS remotely)

**Access:**
- Dedicated management network (separate from production)
- VPN access for Chris from anywhere
- Independent of server OS (works even if OS crashes)

**Use Cases:**
- Deploy OS from home
- Troubleshoot boot issues
- Monitor hardware health
- Graceful shutdown during extended outage
- Emergency recovery without site visit

---

## Monitoring & Alerting

### Server Health Monitoring
- IPMI sensors (temperature, fan speed, power)
- SMART data on all drives (predict failures)
- RAID status monitoring
- UPS status and battery health
- Network interface status

### Application Monitoring
- PostgreSQL query performance
- Web application response times
- API endpoint health checks
- Database connection pool status
- Disk space utilization

### Alerting Channels
- Email alerts (critical issues)
- SMS alerts (server down)
- Slack/webhook integration (optional)
- Dashboard for at-a-glance status

**Alert Scenarios:**
- Drive SMART warnings (order replacement)
- High temperature (check cooling)
- UPS on battery (power issue)
- Database slow queries (optimize)
- Disk space low (clean up)

---

## Security Considerations

### Physical Security
- Server rack in locked office/closet
- IPMI on isolated management network
- UPS tamper alerts

### Network Security
- OPNsense firewall between internet and server
- VLAN segmentation (management, production, guest)
- VPN for remote access (no direct internet exposure)
- Fail2ban for SSH brute force protection

### Data Security
- Encrypted backups (AES-256)
- TLS/SSL for all web traffic
- Database access restricted to application only
- Regular security updates (automated where possible)

---

## Deployment Timeline

### Phase 0: Planning (Current)
- Hardware specification: ✅ Complete
- Budget approval: Pending
- Vendor selection: TBD

### Phase 1: Hardware Procurement (Week 1)
- Order all components
- Delivery: 3-5 business days

### Phase 2: Assembly & Burn-In (Week 1-2)
- Assemble server and router
- Install operating systems
- Configure RAID arrays
- 48-hour stress test
- Verify IPMI functionality

### Phase 3: Software Deployment (Week 2-3)
- Deploy FSM application
- Import production data
- Configure backups
- Set up monitoring
- Performance testing

### Phase 4: Parallel Operation (Week 3-8)
- Run alongside ServiceFusion
- Michele uses both systems
- Verify data accuracy
- Build confidence
- Identify any issues

### Phase 5: Cutover (Week 8+)
- Final data migration
- DNS/network reconfiguration
- Disable ServiceFusion accounts
- Monitor closely for 2 weeks
- Celebrate success 🎉

**Total Time: Procurement → Production: 2-3 weeks**

---

## Maintenance Plan

### Daily (Automated)
- Backup verification
- Health check monitoring
- Log review (automated)

### Weekly (5 min manual check)
- Review monitoring dashboard
- Check for system updates
- Verify backup success

### Monthly (30 min)
- Test backup restore procedure
- Review disk space trends
- Check for firmware updates
- Physical inspection (dust, temps)

### Quarterly (2 hours)
- Failover testing (simulate failures)
- Security patch review
- Performance optimization review
- Capacity planning check

### Annually (4 hours)
- Full disaster recovery test
- UPS battery replacement (if needed)
- Hardware health assessment
- Documentation updates

---

## Risk Assessment & Mitigation

### Risk: Hardware Failure
**Likelihood:** Low (quality components, redundancy)
**Impact:** Medium (2-3 hour recovery with spares)
**Mitigation:**
- RAID1 on all storage
- Spare parts on hand
- Good backups
- IPMI for remote diagnosis

### Risk: Power Outage
**Likelihood:** Medium (varies by location)
**Impact:** Low (UPS provides graceful shutdown)
**Mitigation:**
- UPS with 20 min runtime
- Automatic shutdown scripts
- Dual internet (one on battery backup)

### Risk: Network Failure
**Likelihood:** Low (dual internet)
**Impact:** Low (automatic failover)
**Mitigation:**
- Dual internet connections
- LACP bonding on critical paths
- OPNsense redundancy

### Risk: Data Corruption
**Likelihood:** Very Low (ECC RAM, RAID, backups)
**Impact:** Low (restore from backup)
**Mitigation:**
- ECC memory
- PostgreSQL WAL archiving
- Point-in-time recovery
- 3-2-1 backup strategy

### Risk: Software Bug
**Likelihood:** Medium (custom software)
**Impact:** Low to Medium (depends on bug)
**Mitigation:**
- Thorough testing before deployment
- Parallel operation during transition
- Easy rollback capability
- Good documentation

### Risk: Security Breach
**Likelihood:** Low (internal only, no internet exposure)
**Impact:** High (if occurs)
**Mitigation:**
- Firewall protection
- VPN for remote access
- Regular security updates
- Principle of least privilege
- Encrypted backups

---

## Future Expansion Paths

### If Load Increases 2-3x
- **RAM:** Upgrade to 128GB ($280)
- **Storage:** Add more NVMe capacity
- **No CPU upgrade needed** (12 cores handle 3x load easily)

### If Geographic Expansion
- **Second Site:** Deploy identical hardware
- **Database Replication:** PostgreSQL streaming replication
- **Load Balancing:** HAProxy between sites
- **Cost:** ~$4,500 per site

### If Feature Set Expands
- **More Storage:** Add NVMe as needed
- **GPU Acceleration:** Add GPU for AI features (future)
- **10GbE:** Upgrade network if needed
- **Current hardware supports all this**

---

## Success Metrics

### Technical Metrics
- **Uptime Target:** 99.5% (43 hours/year downtime acceptable)
- **Response Time:** <200ms for page loads
- **Database Query Time:** <50ms for typical queries
- **Backup Success Rate:** 100%
- **Recovery Time Objective:** 2-3 hours for complete failure

### Business Metrics
- **Michele's Time Savings:** 10+ hours/week
- **Statement Generation Time:** <2 minutes (vs 30+ minutes)
- **Invoice Error Rate:** <1% (vs 5% with SF→QB sync)
- **Cost Savings:** $25,000+/year
- **Payback Period:** 2.1 months

### User Satisfaction
- Michele can generate statements easily
- Office staff find scheduler responsive
- Techs prefer mobile interface
- No complaints about system speed

---

## Conclusion

**This hardware plan provides:**
- ✅ Production-grade reliability
- ✅ Proper redundancy at all critical points
- ✅ Remote management capability
- ✅ Room for growth (3x capacity headroom)
- ✅ Excellent power efficiency
- ✅ Professional presentation
- ✅ Reasonable cost ($4,480 all-in)

**System characteristics:**
- Low power (123W average, $11/month)
- High reliability (RAID, UPS, spares, backups)
- Easy maintenance (IPMI, monitoring, automation)
- Fast performance (NVMe, 2.5GbE, modern CPU)
- Future-proof (can scale 3x without hardware changes)

**Decision Point:**
Hardware plan is complete and ready for implementation when software development reaches production-ready state (Phase 0.6).

**Next Steps:**
1. Complete software development (Phase 0: Statement Generator)
2. Validate business case with Michele
3. Get budget approval ($4,480)
4. Order hardware
5. Build and deploy

---

*Document will be updated as requirements evolve during software development phase.*
