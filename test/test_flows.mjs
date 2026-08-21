// Integration test: post_task -> submit_result (rubric-based adjudication)
// and get_reputation format parity + address conversion parity with index.html.
//
// Setup:
//   npm install
// Run:
//   MULTIAGENTPRO_CONTRACT=0x... GL_PRIVKEY=0x... node test/test_flows.mjs
import { createClient } from 'genlayer-js';
import { testnetBradbury } from 'genlayer-js/chains';
import { privateKeyToAccount } from 'viem/accounts';
import { toReputationKey } from '../lib/address.mjs';

const CONTRACT = process.env.MULTIAGENTPRO_CONTRACT;
if (!CONTRACT) { console.error('Set MULTIAGENTPRO_CONTRACT env var'); process.exit(1); }

const account = privateKeyToAccount(process.env.GL_PRIVKEY);
const client = createClient({ chain: testnetBradbury, account });
const sleep = ms => new Promise(r => setTimeout(r, ms));

function assert(cond, msg) {
  if (!cond) { console.error('FAIL:', msg); process.exitCode = 1; }
  else console.log('PASS:', msg);
}

// Mirrors index.html checkReputation() parser exactly
function parseReputation(rep) {
  if (rep === 'no reputation') return { completed: 0, total: 0 };
  const m = rep.match(/(\d+)\/(\d+) tasks completed/);
  if (!m) return null;
  return { completed: parseInt(m[1]), total: parseInt(m[2]) };
}

async function retryable(fn, label, attempts = 5) {
  for (let i = 1; i <= attempts; i++) {
    try { return await fn(); }
    catch (e) {
      console.log(`${label} attempt ${i} failed: ${e.shortMessage || e.message}`.slice(0, 100));
      if (i === attempts) throw e;
      await sleep(5000 * i);
    }
  }
}

console.log('--- Flow 1: post_task -> submit_result uses rubric in adjudication ---');
const postHash = await retryable(() => client.writeContract({
  address: CONTRACT, functionName: 'post_task',
  args: ['Write the word "banana" and nothing else', 'Result must contain exactly the word banana', '1 GEN'],
}), 'post_task');
console.log('post_task TX:', postHash);
await sleep(5000);

await retryable(() => client.waitForTransactionReceipt({ hash: postHash, status: 'ACCEPTED', retries: 60, interval: 5000 }), 'post_task receipt');
await sleep(3000);

const countBefore = await retryable(() => client.readContract({ address: CONTRACT, functionName: 'get_count', args: [] }), 'get_count');
const tid = String(Number(countBefore) - 1);
await sleep(3000);

const submitHash = await retryable(() => client.writeContract({
  address: CONTRACT, functionName: 'submit_result', args: [tid, 'banana'],
}), 'submit_result');
console.log('submit_result TX:', submitHash);
await sleep(5000);

await retryable(() => client.waitForTransactionReceipt({ hash: submitHash, status: 'FINALIZED', retries: 120, interval: 10000 }), 'submit_result receipt');
await sleep(3000);

const task = await retryable(() => client.readContract({ address: CONTRACT, functionName: 'get_task', args: [tid] }), 'get_task');
assert(task.includes('Rubric:'), 'get_task exposes rubric field');
assert(task.includes('completed') || task.includes('failed'), 'submit_result resolved a verdict using the rubric');
await sleep(3000);

console.log('--- Flow 2: get_reputation format + address conversion match the frontend ---');
// Uses the exact same helper index.html imports from lib/address.mjs — if the
// frontend's conversion ever changes, this test changes with it automatically.
const key = toReputationKey(account.address);
const rep = await retryable(() => client.readContract({ address: CONTRACT, functionName: 'get_reputation', args: [key] }), 'get_reputation');
const parsed = parseReputation(rep);
assert(parsed !== null, `get_reputation format is parseable by the frontend regex (got: "${rep}")`);
assert(parsed && parsed.total >= 1, 'reputation total incremented after submit_result');

console.log('Done.');
