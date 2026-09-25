import { ApiError } from "../../shared/api";
import type { ChannelMemberRole } from "./types";

export type MemberAction = "invite" | "change_role" | "remove";

export function canManageChannelMembers(
  role: ChannelMemberRole | null | undefined,
): boolean {
  return role === "owner" || role === "admin";
}

export function getMemberActionErrorMessage(
  action: MemberAction,
  error: unknown,
): string {
  if (!(error instanceof ApiError)) {
    return getFallbackMessage(action);
  }

  if (error.status === 403) {
    return getForbiddenMessage(action);
  }

  if (action === "invite" && error.status === 404) {
    return "No account exists with that email address.";
  }

  if (action === "invite" && error.status === 409) {
    return "That person is already a member of this channel.";
  }

  if (action === "remove" && error.status === 404) {
    return "That member is no longer in this channel.";
  }

  if (
    (action === "change_role" || action === "remove") &&
    error.status === 409
  ) {
    return "A channel must retain at least one owner.";
  }

  return error.message;
}

function getForbiddenMessage(action: MemberAction): string {
  if (action === "invite") {
    return "You do not have permission to invite members to this channel.";
  }
  if (action === "change_role") {
    return "You do not have permission to change member roles in this channel.";
  }
  return "You do not have permission to remove members from this channel.";
}

function getFallbackMessage(action: MemberAction): string {
  if (action === "invite") {
    return "Unable to invite this member. Please try again.";
  }
  if (action === "change_role") {
    return "Unable to update this member's role. Please try again.";
  }
  return "Unable to remove this member. Please try again.";
}
