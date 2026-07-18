# Solana Token Analytics - Vue.js Frontend

Vue 3 + Vite frontend for the Solana Token Analytics backend (`backend/api_server.py`).

## Backend API Contract

Backend runs at `http://localhost:8000` (start with `uvicorn backend.api_server:app --reload --port 8000`).

### REST Endpoints

#### GET /api/token/{mint}
Get token information with real-time price.

**Response:**
```json
{
  "mint": "ABC123...",
  "symbol": "TOKEN",
  "name": "Token Name",
  "price_usd": 0.00004,
  "price_sol": 0.0002,
  "market_cap": 40000,
  "liquidity": 5000,
  "volume_24h": 10000,
  "price_change_24h": 15.5,
  "price_change_1h": 2.3,
  "price_change_5m": 0.5,
  "dex": "raydium"
}
```

#### GET /api/token/{mint}/holders
Get big wallet holders ($10k+ holdings).

**Query params:**
- `min_value_usd` (optional): Minimum USD value, default 1000

**Response:**
```json
[
  {
    "address": "ABC123...",
    "amount": 1000000,
    "value_usd": 50000,
    "label": "Jupiter v6",
    "is_smart": true,
    "percentage": 5.5
  }
]
```

#### GET /api/token/{mint}/transactions
Get recent big transactions.

**Response:**
```json
[
  {
    "signature": "sig123...",
    "type": "SWAP",
    "from_address": "ABC...",
    "to_address": "DEF...",
    "amount": 1000000,
    "timestamp": 1705312800
  }
]
```

#### GET /api/wallet/{address}/analyze
Analyze a wallet's trading history.

**Response:**
```json
{
  "total_txs": 150,
  "swaps": 100,
  "nft_trades": 20,
  "transfers": 30,
  "win_rate": 0,
  "avg_hold_time": 0
}
```

### WebSocket Endpoints

#### ws://localhost:8000/ws/token/{mint}
Real-time price updates for a token. Client sends `ping`, server replies `pong`.

**Message format (every 5 seconds):**
```json
{
  "type": "price_update",
  "data": {
    "price_usd": 0.00004,
    "price_sol": 0.0002,
    "market_cap": 40000,
    "liquidity": 5000,
    "volume_24h": 10000,
    "price_change_24h": 15.5,
    "price_change_1h": 2.3,
    "price_change_5m": 0.5
  },
  "timestamp": "2024-01-15T10:30:00"
}
```

#### ws://localhost:8000/ws/wallet/{address}
Real-time wallet monitoring via Solana WebSocket.

**Message format:**
```json
{
  "type": "account_update",
  "data": { /* Solana account data */ },
  "timestamp": "2024-01-15T10:30:00"
}
```

## Implemented Components

| Component | Purpose |
| --- | --- |
| `src/components/TokenSearch.vue` | Mint address input + search |
| `src/components/TokenInfo.vue` | Price, market cap, liquidity, volume, change stats |
| `src/components/PriceChart.vue` | Real-time line chart via Chart.js, fed by `/ws/token/{mint}` |
| `src/components/WhaleList.vue` | Big wallet holders table (`/api/token/{mint}/holders`) |
| `src/components/TransactionFeed.vue` | Recent big transactions (`/api/token/{mint}/transactions`) |
| `src/components/WalletAnalyzer.vue` | Wallet analysis stats (`/api/wallet/{address}/analyze`) |
| `src/views/TokenView.vue` | Token page: search + info + chart + whales + txs |
| `src/views/WalletView.vue` | Wallet page: analyze + live account updates via `/ws/wallet/{address}` |
| `src/stores/token.js` | Pinia store for token state |
| `src/services/api.js` | Axios REST client |
| `src/services/websocket.js` | WebSocket helpers with auto-reconnect + ping/pong |

## Setup

```bash
cd web
npm install
npm run dev
```

The dev server runs on `http://localhost:5173` and proxies `/api` and `/ws` to `http://localhost:8000` (see `vite.config.js`).

### Environment (optional)
Create `web/.env.local`:
```
VITE_API_BASE=http://localhost:8000
VITE_WS_BASE=ws://localhost:8000
```

### package.json

If `package.json` is missing, create it with:

```json
{
  "name": "solana-token-analytics-web",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.7",
    "axios": "^1.6.7",
    "chart.js": "^4.4.1",
    "@vueuse/core": "^10.7.2"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.10"
  }
}
```

## Stack
- Vue 3 (Composition API, `<script setup>`)
- Vite 5
- Vue Router 4
- Pinia 2
- Axios (REST)
- Chart.js (price chart)
- Native WebSocket with auto-reconnect + ping/pong keep-alive