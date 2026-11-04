// The TOTP code check of the login and setup forms. The backend ignores spaces.
export const TOTP_CODE_ERROR = "Enter the 6-digit code from your authenticator app.";

export function isTotpCode(code: string): boolean {
  return /^\d{6}$/.test(code.replace(/\s/g, ""));
}
