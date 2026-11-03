// TOTP codes (RFC 6238: SHA-1, 6 digits, 30 s), as an authenticator app makes them.
import { createHmac } from "node:crypto";

const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
const STEP_SECONDS = 30;

function base32Decode(text: string): Buffer {
  let bits = "";
  for (const char of text.replace(/=+$/, "").toUpperCase()) {
    const value = BASE32.indexOf(char);
    if (value === -1) throw new Error("Bad base32 secret");
    bits += value.toString(2).padStart(5, "0");
  }
  const bytes = bits.match(/.{8}/g) ?? [];
  return Buffer.from(bytes.map((byte) => parseInt(byte, 2)));
}

export function totp(secret: string, step: number): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const hmac = createHmac("sha1", base32Decode(secret)).update(counter).digest();
  const offset = (hmac.at(-1) ?? 0) & 0xf;
  const code = (hmac.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return code.toString().padStart(6, "0");
}

const currentStep = () => Math.floor(Date.now() / 1000 / STEP_SECONDS);
let lastStep = 0;

/**
 * A code that WT did not see yet. WT rejects a step that it already used (replay), so this
 * waits for the next step when needed (up to 30 s).
 */
export async function freshTotp(secret: string): Promise<string> {
  while (currentStep() <= lastStep) await new Promise((resolve) => setTimeout(resolve, 500));
  lastStep = currentStep();
  return totp(secret, lastStep);
}
