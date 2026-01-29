# Production Hardware Plan for FSM System
**Created**: 2026-01-28 (from planning session 2026-01-15)
**Status**: Planned, Not Yet Purchased

---

## 🎯 Goals

Build a production-grade, self-hosted infrastructure for business-critical FSM system supporting:
- 250 jobs/day at peak (Kleanit)
- 25 field technicians
- 5 office staff
- 4 companies
- Zero downtime tolerance

---

## 🖥️ Main Server Specifications

### CPU
**AMD Ryzen 9 7900** - $430
- 12 cores / 24 threads
- 65W TDP (energy efficient)
- Excellent multi-threaded performance
- Perfect for database + application server

### Motherboard
**ASRock Rack X570D4I-2T** - $500
- **Dual 10GbE SFP+** (for LACP bonding)
- **IPMI built-in** (ASRock Rack BMC)
- Mini-ITX (rackmount friendly)
- ECC RAM support
- Industrial-grade components
- Remote management capabilities

### RAM
**64GB (2x32GB) ECC UDIMM DDR4** - $240
- Kingston or Crucial server-grade
- ECC for data integrity (critical for business data)
- Sufficient for PostgreSQL + Redis + applications

### Storage
- **Boot**: 2x 500GB Samsung 990 Pro (RAID1) - $120
- **Data**: 2x 2TB Samsung 990 Pro (RAID1) - $360
- **Backup**: 2x 4TB WD Red (RAID1) - $180

### Power & Case
- **PSU**: EVGA SuperNOVA 750 P6 80+ Platinum - $120
- **Case**: 2U Rackmount - $300
- **UPS**: CyberPower PR1500LCDRTXL2U - $550

**Main Server Total: ~$2,800**

---

## 🔥 OPNsense Router/Firewall

### Components
- **CPU**: AMD Ryzen 5 7600 - $220
- **Motherboard**: ASRock B650M-HDV/M.2 - $110
- **RAM**: 32GB DDR5 - $100
- **Boot Storage**: 2x 256GB NVMe (RAID1) - $60
- **Network Card**: Intel I350-T4 (Quad 1GbE) - $80
- **PSU**: Corsair RM550x 80+ Gold - $90
- **Case**: 1U Rackmount - $150

**OPNsense Router Total: ~$810**

---

## 🔌 Networking Infrastructure

- **2x Managed 2.5GbE Switches (8-port)** - $200
- **Cat6 Cabling** - $50
- **Fiber Patch Cables** - $40

**Total Networking: $290**

---

## 🏗️ Rack & Organization

- **12U Wall-Mount Rack** - $200
- **Cable Management Kit** - $50
- **1U Shelf for Switches** - $30

**Total Rack: $280**

---

## 🛠️ Spare Parts Kit

- **Spare PSU** - $120
- **Spare Boot NVMe** - $60
- **Spare RAM Module** - $120

**Total Spare Parts: $300**

---

## 💰 Complete Cost Breakdown

### Recommended Production Setup
- Main Server: $2,800
- OPNsense Router: $810
- Spare Parts: $300
- Networking: $290
- Rack: $280
- **Total: $4,480**

---

## ⚡ Power Analysis

### Power Consumption
- **Main Server**: 64W idle / 102W typical / 133W peak
- **OPNsense Router**: 47W idle / 71W typical / 96W peak
- **Combined Average**: 123W
- **Monthly Cost**: $10.63 (at $0.12/kWh)
- **Annual Cost**: $128/year

### Savings vs Old Setup (3x Dell Servers)
- **Old**: $870/year
- **New**: $128/year
- **Savings**: $742/year in electricity

---

## 🔄 Internet Redundancy

### Primary: Business Fiber
- Static IP, 500+ Mbps
- SLA guarantee
- Cost: ~$150-250/month

### Backup: 5G Cellular
- Different infrastructure
- 100+ Mbps typical
- Auto-failover via OPNsense
- Cost: ~$75-150/month

### Failover: < 30 seconds automatic

---

## 🔗 LACP Bonding Strategy

**Link Aggregation Control Protocol**:
- Combines multiple network connections
- Automatic failover if one link fails
- Bandwidth aggregation
- Load balancing

**Implementation**:
- Main Server: Dual 10GbE SFP+ ports bonded
- OPNsense: Dual 2.5GbE ports bonded
- Enterprise-grade reliability

---

## 🖥️ Remote Management (IPMI/BMC)

**Built into ASRock Rack Motherboard**:
- Full KVM over IP
- Remote power control
- BIOS access remotely
- Hardware monitoring
- Virtual media mounting
- Works even if OS crashes

---

## 💾 Backup Strategy (3-2-1 Rule)

### 3 Copies
1. Production (mirrored NVMe)
2. Local backup (mirrored HDD)
3. Cloud backup (Backblaze B2)

### 2 Media Types
- NVMe (production)
- HDD (local backup)
- Cloud (offsite)

### 1 Offsite
- Backblaze B2: $3-5/month

### Schedule
- **Continuous**: PostgreSQL WAL archiving
- **Hourly**: Database snapshots
- **Nightly**: Full system backup
- **Weekly**: System image
- **Monthly**: Archive (1 year retention)

### Recovery Times
- Database corruption: < 5 min
- Drive failure: 0 downtime (RAID1)
- Complete server failure: 2-3 hours
- Disaster recovery: 4-8 hours

---

## 🎯 Why This Hardware?

### ECC RAM
- Detects/corrects memory errors
- Prevents data corruption
- Industry standard for servers

### RAID1 Everywhere
- Boot, data, backup all mirrored
- Any drive can fail without downtime

### UPS
- Power protection
- 20 min runtime
- Graceful shutdown

### IPMI
- Fix issues from home
- Monitor remotely
- Save office trips

### Dual Internet
- No single ISP dependency
- Auto-failover in 30 seconds

### LACP Bonding
- Network redundancy
- < 1 second failover

---

## 📊 ROI Analysis

### Current Costs
- ServiceFusion: $18,000/year
- Michele's QB sync time: $25,000/year
- **Total**: $43,000/year

### New System Costs
- Hardware: $4,480 (one-time)
- Hosting/storage: $600/year
- **Annual Savings**: $42,400/year

### Return on Investment
- Break even: ~4 months
- Year 1 net savings: ~$28,000
- Year 2+ savings: ~$42,000/year

---

**Last Updated**: 2026-01-28
**Status**: Planning Complete
**Total Cost**: $4,480
**Annual Savings**: $43,142 (FSM + electricity)
**ROI**: 3-4 months
