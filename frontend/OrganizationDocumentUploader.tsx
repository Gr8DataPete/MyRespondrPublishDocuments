import React, { useState } from "react";

// Simple standalone uploader component that posts to the backend endpoint
// POST /api/organizations/me/documents

export default function OrganizationDocumentUploader() {
  // Read API base from injected env-config at runtime so frontend can talk to a separate backend
  const API_BASE = (window as any).__UPLOAD_DOC_ENV?.API_URL || ''
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const onUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    setResult(null);

    try {
      const form = new FormData();
      form.append("file", file);
      form.append("description", "Uploaded from OrganizationDocumentUploader");

      // Attach Authorization header with access token if present in session
      const storedSession = (window.sessionStorage && sessionStorage.getItem('upload_session')) ? JSON.parse(sessionStorage.getItem('upload_session') || '{}') : null
      const accessToken = storedSession?.access_token || storedSession?.accessToken || null
      const headers: Record<string, string> = {}
      if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`

      const resp = await fetch(`${API_BASE}/api/organizations/me/documents`, {
        method: "POST",
        body: form,
        credentials: "include",
        headers,
      });

      let data: any = null
      let text: string | null = null
      try {
        data = await resp.json()
      } catch (e) {
        text = await resp.text().catch(() => null)
        console.warn('Non-JSON upload response', e)
      }
      console.log('[OrganizationDocumentUploader] upload response', { status: resp.status, data, text })
      if (!resp.ok) {
        if (data && data.error) setError(String(data.error))
        else if (text) setError(text)
        else setError(`Upload failed (status ${resp.status})`)
      } else {
        setResult(data)
      }
    } catch (e: any) {
      setError(e.message || String(e));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ padding: 12 }}>
      <h3>Upload Organization Document</h3>
      <input type="file" onChange={onFileChange} />
      <div style={{ marginTop: 8 }}>
        <button onClick={onUpload} disabled={!file || uploading}>
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </div>

      {error && (
        <div style={{ color: "red", marginTop: 12 }}>Error: {error}</div>
      )}

      {result && (
        <div style={{ color: "green", marginTop: 12 }}>
          <div>Uploaded document id: {result.document_id}</div>
          <div>
            Public URL: {result.public_url ? (
              <a href={result.public_url} target="_blank" rel="noreferrer">Open</a>
            ) : (
              "(no public url)"
            )}
          </div>
        </div>
      )}
    </div>
  );
}
