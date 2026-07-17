#!/usr/bin/env node
/**
 * Fetch DLMM bin ranges for positions
 * Requires: @meteora-ag/dlmm, @solana/web3.js
 */

const { Connection, PublicKey } = require('@solana/web3.js');

const RPC_URL = process.env.RPC_URL || 'https://api.mainnet-beta.solana.com';
const WALLET_ADDRESS = process.env.WALLET_ADDRESS;

async function fetchBinRanges() {
    if (!WALLET_ADDRESS) {
        console.error('WALLET_ADDRESS not set');
        process.exit(1);
    }

    const connection = new Connection(RPC_URL, 'confirmed');
    
    try {
        // Fetch positions from Meteora API
        const response = await fetch(`https://dlmm-api.meteora.ag/position/${WALLET_ADDRESS}`);
        const positions = await response.json();
        
        if (!Array.isArray(positions) || positions.length === 0) {
            console.log(JSON.stringify({ positions: [] }));
            return;
        }

        const results = positions.map(pos => ({
            address: pos.address,
            pair: pos.pair?.name || 'Unknown',
            activeBin: pos.pair?.activeBinId || 0,
            lowerBin: pos.lowerBinId || 0,
            upperBin: pos.upperBinId || 0,
            inRange: (pos.lowerBinId <= pos.pair?.activeBinId) && (pos.pair?.activeBinId <= pos.upperBinId)
        }));

        console.log(JSON.stringify({ positions: results }, null, 2));
        
    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
}

fetchBinRanges();
