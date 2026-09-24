import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  addChannelMember,
  getChannelMembers,
  removeChannelMember,
  updateChannelMemberRole,
} from "./api";
import { setTokenProvider } from "../../shared/api";

describe("channel member API", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setTokenProvider(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("fetches the channel member list from the backend contract", async () => {
    const members = [
      {
        id: "member-1",
        user_id: "user-1",
        email: "owner@example.com",
        channel_id: "channel-1",
        role: "owner",
      },
      {
        id: "member-2",
        user_id: "user-2",
        email: "member@example.com",
        channel_id: "channel-1",
        role: "member",
      },
    ];

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(members), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getChannelMembers("channel-1")).resolves.toEqual(members);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/members",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
      }),
    );
  });

  it("posts an email-based member invite with the member role", async () => {
    const membership = {
      id: "membership-1",
      user_id: "user-2",
      channel_id: "channel-1",
      role: "member",
    };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(membership), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      addChannelMember("channel-1", {
        email: "member@example.com",
        role: "member",
      }),
    ).resolves.toEqual(membership);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/members",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "member@example.com",
          role: "member",
        }),
      }),
    );
  });

  it("patches a channel member role", async () => {
    const membership = {
      id: "membership-1",
      user_id: "user-2",
      channel_id: "channel-1",
      role: "admin",
    };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(membership), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      updateChannelMemberRole("channel-1", "user-2", { role: "admin" }),
    ).resolves.toEqual(membership);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/members/user-2",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ role: "admin" }),
      }),
    );
  });

  it("deletes a channel member", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));

    await expect(
      removeChannelMember("channel-1", "user-2"),
    ).resolves.toBeNull();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/members/user-2",
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
      }),
    );
  });
});
