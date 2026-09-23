import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getChannelMembers } from "./api";
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
});
