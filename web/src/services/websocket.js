const base = import.meta.env.VITE_WS_BASE || 'ws://localhost:8000'

export function createTokenSocket(mint, onUpdate, onStatus) {
  let ws = null
  let pingTimer = null
  let closed = false

  function connect() {
    ws = new WebSocket(`${base}/ws/token/${mint}`)
    onStatus?.('connecting')

    ws.onopen = () => {
      onStatus?.('connected')
      pingTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) ws.send('ping')
      }, 25000)
    }

    ws.onmessage = (ev) => {
      if (ev.data === 'pong') return
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'price_update') onUpdate?.(msg.data, msg.timestamp)
      } catch (e) {
        // ignore malformed
      }
    }

    ws.onerror = () => onStatus?.('error')
    ws.onclose = () => {
      clearInterval(pingTimer)
      onStatus?.('closed')
      if (!closed) setTimeout(connect, 3000)
    }
  }

  connect()

  return {
    close() {
      closed = true
      clearInterval(pingTimer)
      ws?.close()
    }
  }
}

export function createWalletSocket(address, onUpdate, onStatus) {
  let ws = null
  let closed = false

  function connect() {
    ws = new WebSocket(`${base}/ws/wallet/${address}`)
    onStatus?.('connecting')

    ws.onopen = () => onStatus?.('connected')
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'account_update') onUpdate?.(msg.data, msg.timestamp)
      } catch (e) {
        // ignore
      }
    }
    ws.onerror = () => onStatus?.('error')
    ws.onclose = () => {
      onStatus?.('closed')
      if (!closed) setTimeout(connect, 3000)
    }
  }

  connect()

  return {
    close() {
      closed = true
      ws?.close()
    }
  }
}