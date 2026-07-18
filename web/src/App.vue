<template>
  <div class="app-shell">
    <header>
      <h1 style="font-size:20px;margin:0 0 4px">Solana Token Analytics</h1>
      <p style="color:var(--muted);margin:0 0 16px;font-size:13px">
        Real-time token price, big wallet holders, and transactions
      </p>
      <nav class="nav">
        <router-link to="/token">Token</router-link>
        <router-link to="/wallet">Wallet Analyzer</router-link>
      </nav>
    </header>
    <router-view />
  </div>
</template>

<script setup></script>