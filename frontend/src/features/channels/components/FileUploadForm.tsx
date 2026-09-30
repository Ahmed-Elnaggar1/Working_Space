import { useRef, useState, type FormEvent } from "react";
import { uploadChannelFile } from "../api";
import { canUploadFiles, getFileActionErrorMessage } from "../fileManagement";
import type { ChannelFile, ChannelMemberRole } from "../types";
import styles from "./FileUploadForm.module.css";

const ALLOWED_EXTENSIONS = [".pdf", ".txt"];

interface FileUploadFormProps {
  channelId: string;
  userRole: ChannelMemberRole | null | undefined;
  onUploaded: (file: ChannelFile) => void;
}

export function FileUploadForm({
  channelId,
  userRole,
  onUploaded,
}: FileUploadFormProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Per permissions.md and S7-04: upload control is hidden for read_only members
  if (!canUploadFiles(userRole)) {
    return null;
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    setError(null);
    setSuccessMessage(null);
    const file = event.target.files?.[0] || null;

    if (file) {
      const lowerName = file.name.toLowerCase();
      const isAllowed = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
      if (!isAllowed) {
        setError(
          "Unsupported file type. Only PDF (.pdf) and plain text (.txt) files are supported.",
        );
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
        return;
      }
    }

    setSelectedFile(file);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setError("Please select a file to upload.");
      return;
    }

    setIsUploading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const newFile = await uploadChannelFile(channelId, selectedFile);
      setSuccessMessage(`Successfully uploaded "${selectedFile.name}".`);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      onUploaded(newFile);
    } catch (uploadError) {
      setError(getFileActionErrorMessage("upload", uploadError));
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <label className={styles.label} htmlFor="channel-file-input">
        Upload file
      </label>
      <p className={styles.hint}>
        Supported formats: PDF (.pdf) and plain text (.txt).
      </p>

      <div className={styles.controls}>
        <input
          ref={fileInputRef}
          id="channel-file-input"
          className={styles.fileInput}
          type="file"
          accept=".pdf,.txt"
          disabled={isUploading}
          onChange={handleFileChange}
          aria-label="Choose file to upload"
        />
        <button
          className={styles.uploadButton}
          type="submit"
          disabled={isUploading || !selectedFile}
        >
          {isUploading ? "Uploading..." : "Upload"}
        </button>
      </div>

      {isUploading && selectedFile && (
        <div className={styles.progressContainer} aria-live="polite">
          <div className={styles.progressInfo}>
            <span>Uploading {selectedFile.name}...</span>
            <span>In progress</span>
          </div>
          <div className={styles.progressBarTrack}>
            <div className={styles.progressBarFill} />
          </div>
        </div>
      )}

      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      {successMessage && (
        <p className={styles.success} role="status">
          {successMessage}
        </p>
      )}
    </form>
  );
}
