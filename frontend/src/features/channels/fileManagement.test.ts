import { describe, expect, it } from "vitest";
import { ApiError } from "../../shared/api";
import {
  canDeleteFile,
  canRetryIngestion,
  canUploadFiles,
  getFileActionErrorMessage,
  hasActiveIngestion,
  INGESTION_POLL_INTERVAL_MS,
} from "./fileManagement";
import type { ChannelFile } from "./types";

describe("channel file management policy", () => {
  it("defines the standard 3-second polling interval per S7-06", () => {
    expect(INGESTION_POLL_INTERVAL_MS).toBe(3000);
  });

  describe("canUploadFiles", () => {
    it.each([
      ["owner", true],
      ["admin", true],
      ["member", true],
      ["read_only", false],
      [undefined, false],
    ])("allows upload for %s: %s", (role, expected) => {
      expect(canUploadFiles(role as never)).toBe(expected);
    });
  });

  describe("canDeleteFile", () => {
    const ownerUser = "user-owner";
    const memberUser = "user-member";
    const otherUser = "user-other";

    it("allows owner and admin to delete any file", () => {
      expect(canDeleteFile("owner", otherUser, ownerUser)).toBe(true);
      expect(canDeleteFile("owner", ownerUser, ownerUser)).toBe(true);
      expect(canDeleteFile("admin", otherUser, ownerUser)).toBe(true);
      expect(canDeleteFile("admin", ownerUser, ownerUser)).toBe(true);
    });

    it("allows member to delete only their own uploaded file", () => {
      expect(canDeleteFile("member", memberUser, memberUser)).toBe(true);
      expect(canDeleteFile("member", otherUser, memberUser)).toBe(false);
    });

    it("denies read_only from deleting any file including their own", () => {
      expect(canDeleteFile("read_only", "user-ro", "user-ro")).toBe(false);
      expect(canDeleteFile("read_only", otherUser, "user-ro")).toBe(false);
    });

    it("denies undefined role or missing user from deleting files", () => {
      expect(canDeleteFile(undefined, otherUser, undefined)).toBe(false);
      expect(canDeleteFile("member", memberUser, undefined)).toBe(false);
    });
  });

  describe("canRetryIngestion", () => {
    it("only allows retry on failed files for roles with upload permission", () => {
      expect(canRetryIngestion("owner", "failed")).toBe(true);
      expect(canRetryIngestion("admin", "failed")).toBe(true);
      expect(canRetryIngestion("member", "failed")).toBe(true);
      expect(canRetryIngestion("read_only", "failed")).toBe(false);

      expect(canRetryIngestion("owner", "pending")).toBe(false);
      expect(canRetryIngestion("owner", "processing")).toBe(false);
      expect(canRetryIngestion("owner", "completed")).toBe(false);
    });
  });

  describe("hasActiveIngestion", () => {
    const makeFile = (status: ChannelFile["ingestion_status"]): ChannelFile => ({
      id: "f1",
      channel_id: "c1",
      filename: "test.pdf",
      storage_path: "path",
      uploaded_by: "u1",
      ingestion_status: status,
      created_at: "2026-09-24T00:00:00Z",
    });

    it("detects pending or processing files", () => {
      expect(hasActiveIngestion([makeFile("completed"), makeFile("pending")])).toBe(true);
      expect(hasActiveIngestion([makeFile("processing")])).toBe(true);
      expect(hasActiveIngestion([makeFile("completed"), makeFile("failed")])).toBe(false);
      expect(hasActiveIngestion([])).toBe(false);
    });
  });

  describe("getFileActionErrorMessage", () => {
    it.each([
      ["upload", "You do not have permission to upload files to this channel."],
      ["delete", "You do not have permission to delete this file."],
      ["retry", "You do not have permission to retry ingestion for this file."],
      ["download", "You do not have permission to download files from this channel."],
      ["list", "You do not have permission to view files in this channel."],
    ] as const)("returns non-generic 403 message for %s", (action, expected) => {
      expect(
        getFileActionErrorMessage(
          action,
          new ApiError(403, "PERMISSION_DENIED", "Forbidden"),
        ),
      ).toBe(expected);
    });

    it("returns specific 404 messages", () => {
      expect(
        getFileActionErrorMessage(
          "download",
          new ApiError(404, "NOT_FOUND", "Not found"),
        ),
      ).toBe("File not found.");
      expect(
        getFileActionErrorMessage(
          "delete",
          new ApiError(404, "NOT_FOUND", "Not found"),
        ),
      ).toBe("File not found.");
      expect(
        getFileActionErrorMessage(
          "list",
          new ApiError(404, "NOT_FOUND", "Not found"),
        ),
      ).toBe("Channel not found.");
    });

    it("returns specific 400 messages", () => {
      expect(
        getFileActionErrorMessage(
          "retry",
          new ApiError(400, "BAD_REQUEST", "Cannot retry completed"),
        ),
      ).toBe("Completed file ingestions cannot be retried.");

      expect(
        getFileActionErrorMessage(
          "upload",
          new ApiError(
            400,
            "BAD_REQUEST",
            "Unsupported file type. Only PDF (.pdf) and plain text (.txt) files are supported.",
          ),
        ),
      ).toBe(
        "Unsupported file type. Only PDF (.pdf) and plain text (.txt) files are supported.",
      );
    });

    it("falls back gracefully on unknown errors", () => {
      expect(getFileActionErrorMessage("upload", new Error("Unexpected error"))).toBe(
        "Unable to upload file. Please try again.",
      );
      expect(getFileActionErrorMessage("download", "some string error")).toBe(
        "Unable to download file. Please try again.",
      );
    });
  });

  describe("S7-13 role-based UI visibility matrix", () => {
    // Note per Architecture.md §10 and S7-13:
    // UI visibility checks are a UX convenience and never a security boundary.
    // The backend authorization layer enforces role permissions on every request regardless.
    const myId = "my-user-id";
    const otherId = "other-user-id";

    it.each([
      {
        role: "owner" as const,
        canUpload: true,
        canDeleteOwn: true,
        canDeleteAny: true,
      },
      {
        role: "admin" as const,
        canUpload: true,
        canDeleteOwn: true,
        canDeleteAny: true,
      },
      {
        role: "member" as const,
        canUpload: true,
        canDeleteOwn: true,
        canDeleteAny: false,
      },
      {
        role: "read_only" as const,
        canUpload: false,
        canDeleteOwn: false,
        canDeleteAny: false,
      },
    ])(
      "verifies visibility matrix for role: $role matches permissions.md",
      ({ role, canUpload, canDeleteOwn, canDeleteAny }) => {
        expect(canUploadFiles(role)).toBe(canUpload);
        expect(canDeleteFile(role, myId, myId)).toBe(canDeleteOwn);
        expect(canDeleteFile(role, otherId, myId)).toBe(canDeleteAny);
      },
    );
  });
});
