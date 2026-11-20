import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { Field, TotpCodeField } from "@/components/Field";

test("the field label names the input", () => {
  render(<Field label="Setup token" defaultValue="abc" />);

  expect(screen.getByLabelText("Setup token")).toHaveValue("abc");
});

test("the TOTP code field asks for a one-time code with the number keyboard", async () => {
  const onChange = vi.fn();
  render(<TotpCodeField value="" onChange={onChange} />);
  const input = screen.getByLabelText("TOTP code");

  expect(input).toHaveAttribute("inputmode", "numeric");
  expect(input).toHaveAttribute("autocomplete", "one-time-code");
  expect(input).toBeRequired();
  await userEvent.type(input, "1");
  expect(onChange).toHaveBeenCalledWith("1");
});
