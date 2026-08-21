// Canonical address handling for get_reputation lookups.
// The contract stores reputation keyed by str(gl.message.sender_address),
// a standard "0x..." hex string — pass addresses through unchanged.
// (Previously the frontend base64-encoded the address before lookup,
// which never matched the stored hex key — reputation always showed 0.)
export function toReputationKey(addr) {
  return addr.trim();
}
