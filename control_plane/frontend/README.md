# HydraStream Control Plane - Frontend

This is the SaaS UI layer for the HydraStream platform, built with Next.js, React, and TypeScript.

## Features

- **System Overview Dashboard**: Monitor your streaming infrastructure.
- **Tenant Management**: List, search, and manage isolated tenant environments.
- **Configuration Wizard**: Multi-step form to provision new streaming pipelines (Kafka sources, JDBC sinks).
- **Real-time Metrics**: Visualized metrics for each tenant (mocked until backend integration is ready).
- **dbt Integration**: View generated `profiles.yml` and `vars.json` for each tenant.

## Tech Stack

- **Framework**: Next.js 16 (App Router)
- **State Management**: SWR (Data fetching)
- **Forms**: React Hook Form + Zod
- **Icons**: Lucide React
- **Styling**: Vanilla CSS

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Build for production:
   ```bash
   npm run build
   ```

## Backend Integration

The frontend expects the HydraStream Control Plane API to be running at `http://localhost:8000` (can be overridden via `NEXT_PUBLIC_API_URL` environment variable).
