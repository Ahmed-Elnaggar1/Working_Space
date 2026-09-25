import { describe, expect, it } from "vitest";
import { ApiError } from "../../shared/api";
import {
  canManageChannelMembers,
  getMemberActionErrorMessage,
} from "./memberManagement";

describe("channel member management policy", () => {
  it.each([
    ["owner", true],
    ["admin", true],
    ["member", false],
    ["read_only", false],
    [undefined, false],
  ])("allows management for %s: %s", (role, expected) => {
    expect(canManageChannelMembers(role as never)).toBe(expected);
  });

  it("returns explicit invite errors", () => {
    expect(
      getMemberActionErrorMessage(
        "invite",
        new ApiError(404, "USER_NOT_FOUND", "User not found"),
      ),
    ).toBe("No account exists with that email address.");
    expect(
      getMemberActionErrorMessage(
        "invite",
        new ApiError(409, "MEMBER_EXISTS", "Already a member"),
      ),
    ).toBe("That person is already a member of this channel.");
  });

  it.each([
    ["invite", "You do not have permission to invite members to this channel."],
    [
      "change_role",
      "You do not have permission to change member roles in this channel.",
    ],
    [
      "remove",
      "You do not have permission to remove members from this channel.",
    ],
  ] as const)(
    "returns a non-generic forbidden message for %s",
    (action, expected) => {
      expect(
        getMemberActionErrorMessage(
          action,
          new ApiError(403, "PERMISSION_DENIED", "Permission denied"),
        ),
      ).toBe(expected);
    },
  );

  it("returns explicit last-owner and missing-member errors", () => {
    const lastOwnerError = new ApiError(
      409,
      "LAST_OWNER",
      "A channel must retain at least one owner",
    );

    expect(getMemberActionErrorMessage("change_role", lastOwnerError)).toBe(
      "A channel must retain at least one owner.",
    );
    expect(getMemberActionErrorMessage("remove", lastOwnerError)).toBe(
      "A channel must retain at least one owner.",
    );
    expect(
      getMemberActionErrorMessage(
        "remove",
        new ApiError(404, "MEMBERSHIP_NOT_FOUND", "Membership not found"),
      ),
    ).toBe("That member is no longer in this channel.");
  });
});
