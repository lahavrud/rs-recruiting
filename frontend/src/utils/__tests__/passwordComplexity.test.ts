import { describe, expect, it } from "vitest";

import {
  PASSWORD_MAX_BYTES,
  checkPasswordComplexity,
  isPasswordTooLong,
} from "@/utils/passwordComplexity";

// One of each required character class; padded to the byte length under test.
const CLASSES = "Aa1!";
const padded = (filler: string, count: number): string => CLASSES + filler.repeat(count);

describe("password byte limit (bcrypt 72 bytes)", () => {
  it("counts UTF-8 bytes, not characters", () => {
    const hebrew = padded("א", 35); // 39 chars, 74 bytes
    expect(hebrew.length).toBeLessThan(PASSWORD_MAX_BYTES);
    expect(isPasswordTooLong(hebrew)).toBe(true);
    expect(isPasswordTooLong(padded("א", 34))).toBe(false); // 72 bytes
  });

  it("is reported by checkPasswordComplexity", () => {
    const over = padded("x", 69); // 73 bytes
    const atLimit = padded("x", 68); // 72 bytes
    expect(checkPasswordComplexity(over)).toBe(
      "publicJobs:application.validation.passwordTooLong",
    );
    expect(checkPasswordComplexity(atLimit)).toBeNull();
  });
});
