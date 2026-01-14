# FSM System - Current Status
*Last Updated: 2026-01-14*

## Project Overview
Building custom Field Service Management system to replace ServiceFusion.
- **Companies**: 4 service companies
- **Users**: ~25 field technicians, 5 office staff
- **Scale**: 250 jobs/day at peak season
- **Current Phase**: Phase 0 - Statement Generator

## Business Problem
ServiceFusion costs ~$1,500/month for 4 companies and lacks statement generation.
QuickBooks integration exists but we want to phase out QB entirely.
Michele (AR person) needs accurate customer statements quickly.

## Phase 0 Goals
Build standalone statement generator tool:
- Import unpaid invoices from ServiceFusion exports
- Generate professional PDF statements
- Clean web interface for Michele
- Deployment to production server

**Success Criteria**: Michele can generate statements in <2 minutes

## Current Sprint
Sprint 0.1: Setup & Data Import (Week 1)

## What's Working
✅ GitHub repository created
✅ Project board set up
✅ Directory structure created

## What's In Progress
🔄 Setting up development environment
🔄 Waiting for ServiceFusion data export

## Known Issues
None yet - just getting started!

## Next Steps
1. Export sample invoice data from ServiceFusion
2. Set up PostgreSQL database
3. Design database schema
4. Build data import script

## Key Technical Decisions
*See DECISIONS.md for full list*
