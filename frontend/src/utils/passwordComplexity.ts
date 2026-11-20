/** bcrypt's input limit, mirrored from the backend. It counts UTF-8 *bytes*,
 *  not characters: each Hebrew letter is 2 bytes. */
export const PASSWORD_MAX_BYTES = 72;

/** True when the password exceeds bcrypt's 72-byte limit (backend rejects it). */
export function isPasswordTooLong(val: string): boolean {
  return new TextEncoder().encode(val).length > PASSWORD_MAX_BYTES;
}

/**
 * Mirror of backend `_validate_password_complexity`. Returns an i18n key
 * for the first failing rule, or null when the password satisfies all of:
 *   - at least 8 chars, at most 72 UTF-8 bytes
 *   - at least one uppercase + one lowercase ASCII letter
 *   - at least one digit
 *   - at least one non-alphanumeric character
 */
export function checkPasswordComplexity(val: string): string | null {
  if (val.length < 8) return "publicJobs:application.validation.passwordMin";
  if (isPasswordTooLong(val)) return "publicJobs:application.validation.passwordTooLong";
  if (!/[A-Z]/.test(val)) return "publicJobs:application.validation.passwordUppercase";
  if (!/[a-z]/.test(val)) return "publicJobs:application.validation.passwordLowercase";
  if (!/\d/.test(val)) return "publicJobs:application.validation.passwordDigit";
  if (/^[A-Za-z0-9]*$/.test(val)) return "publicJobs:application.validation.passwordSpecial";
  return null;
}
