const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error("Unable to reach the API. Is the backend running?");
  }

  if (!response.ok) {
    let detail = "The API request could not be completed.";
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep the friendly fallback when the response is not JSON.
    }
    throw new Error(detail);
  }

  return response;
}

export function getHealth() {
  return request("/health").then((response) => response.json());
}

export function createJob(payload) {
  return request("/api/jobs/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).then((response) => response.json());
}

export function getJob(jobId) {
  return request(`/api/jobs/${encodeURIComponent(jobId)}/`).then((response) =>
    response.json(),
  );
}

export function getCertificates(jobId) {
  return request(
    `/api/jobs/${encodeURIComponent(jobId)}/certificates/`,
  ).then((response) => response.json());
}

export async function downloadFile(path) {
  const response = await request(path);
  return response.blob();
}

export function certificateDownloadPath(jobId, certificateId) {
  return `/api/jobs/${encodeURIComponent(
    jobId,
  )}/certificates/${encodeURIComponent(certificateId)}/download`;
}

export function jobDownloadPath(jobId) {
  return `/api/jobs/${encodeURIComponent(jobId)}/download`;
}

export { API_BASE_URL };
