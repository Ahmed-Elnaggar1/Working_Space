import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  addChannelMember,
  deleteChannelFile,
  downloadChannelFile,
  getChannelFiles,
  getChannelMembers,
  getChannelWebSocketUrl,
  removeChannelMember,
  retryFileIngestion,
  updateChannelMemberRole,
  uploadChannelFile,
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

describe("channel websocket URL", () => {
  it("builds a websocket URL with the bearer token and correct scheme", () => {
    expect(getChannelWebSocketUrl("channel-1", "jwt-token")).toBe(
      "ws://localhost:8000/ws/channels/channel-1?token=jwt-token",
    );

    expect(
      getChannelWebSocketUrl(
        "channel-1",
        "jwt-token",
        "https://api.example.com",
      ),
    ).toBe("wss://api.example.com/ws/channels/channel-1?token=jwt-token");
  });
});

describe("channel files API", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setTokenProvider(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("fetches the channel file list", async () => {
    const files = [
      {
        id: "file-1",
        channel_id: "channel-1",
        filename: "notes.pdf",
        storage_path: "channels/channel-1/file-1/notes.pdf",
        uploaded_by: "user-1",
        ingestion_status: "completed",
        ingestion_error: null,
        created_at: "2026-09-24T00:00:00Z",
      },
    ];

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(files), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(getChannelFiles("channel-1")).resolves.toEqual(files);

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/files",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
      }),
    );
  });

  it("uploads a file using FormData", async () => {
    const file = new File(["dummy content"], "report.txt", {
      type: "text/plain",
    });
    const uploadedRecord = {
      id: "file-2",
      channel_id: "channel-1",
      filename: "report.txt",
      storage_path: "channels/channel-1/file-2/report.txt",
      uploaded_by: "user-1",
      ingestion_status: "pending",
      ingestion_error: null,
      created_at: "2026-09-24T00:00:00Z",
    };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(uploadedRecord), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(uploadChannelFile("channel-1", file)).resolves.toEqual(
      uploadedRecord,
    );

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/files",
      expect.objectContaining({
        method: "POST",
        body: expect.any(FormData),
      }),
    );
  });

  it("downloads a channel file and triggers a browser download", async () => {
    const fileContent = "file binary content";
    const blob = new Blob([fileContent], { type: "application/octet-stream" });

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(blob, {
        status: 200,
        headers: {
          "Content-Disposition": 'attachment; filename="notes.pdf"',
          "Content-Type": "application/octet-stream",
        },
      }),
    );

    const mockClick = vi.fn();
    const mockLink = { href: "", download: "", click: mockClick };
    const mockCreateObjectURL = vi
      .fn()
      .mockReturnValue("blob:http://localhost/test-uuid");
    const mockRevokeObjectURL = vi.fn();

    const mockDocument = {
      createElement: vi.fn().mockReturnValue(mockLink),
      body: {
        appendChild: vi.fn(),
        removeChild: vi.fn(),
      },
    };

    const mockWindow = {
      URL: {
        createObjectURL: mockCreateObjectURL,
        revokeObjectURL: mockRevokeObjectURL,
      },
    };

    vi.stubGlobal("window", mockWindow);
    vi.stubGlobal("document", mockDocument);

    await expect(
      downloadChannelFile("channel-1", "file-1", "notes.pdf"),
    ).resolves.toBeUndefined();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/files/file-1/download",
      expect.objectContaining({
        method: "GET",
        credentials: "include",
      }),
    );
    expect(mockCreateObjectURL).toHaveBeenCalled();
    expect(mockClick).toHaveBeenCalled();
    expect(mockRevokeObjectURL).toHaveBeenCalledWith(
      "blob:http://localhost/test-uuid",
    );
    vi.unstubAllGlobals();
  });

  it("retries failed file ingestion", async () => {
    const retriedRecord = {
      id: "file-3",
      channel_id: "channel-1",
      filename: "failed.pdf",
      storage_path: "channels/channel-1/file-3/failed.pdf",
      uploaded_by: "user-1",
      ingestion_status: "pending",
      ingestion_error: null,
      created_at: "2026-09-24T00:00:00Z",
    };

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(retriedRecord), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(retryFileIngestion("channel-1", "file-3")).resolves.toEqual(
      retriedRecord,
    );

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/files/file-3/retry-ingestion",
      expect.objectContaining({
        method: "POST",
      }),
    );
  });

  it("deletes a channel file", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));

    await expect(deleteChannelFile("channel-1", "file-1")).resolves.toBeNull();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8000/channels/channel-1/files/file-1",
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
      }),
    );
  });
});
