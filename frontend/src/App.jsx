import { useCallback, useEffect, useMemo, useState } from "react";
import * as XLSX from "xlsx";
import {
  certificateDownloadPath,
  createJob,
  downloadFile,
  getCertificates,
  getHealth,
  getJob,
  jobDownloadPath,
} from "./services/api";

const TERMINAL_STATES = new Set([
  "COMPLETED",
  "COMPLETED_WITH_ERRORS",
  "FAILED",
]);

const initialForm = {
  title: "Certificate of Completion",
  event_name: "",
  issued_by: "",
  issue_date: new Date().toISOString().slice(0, 10),
};

const MAX_IMPORT_SIZE = 5 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".xlsx", ".xls", ".csv"];

const normalizeHeader = (value) =>
  String(value).trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");

function validateImportedRow(row, fields) {
  if (!row.name.trim()) return "Name is required";
  if (!row.email.trim()) return "Email is required";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(row.email.trim())) {
    return "Invalid email format";
  }
  for (const field of fields) {
    const value = String(row.data?.[field.key] ?? "").trim();
    if (field.required && !value) return `${field.label} is required`;
    if (!value) continue;
    if (field.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      return `${field.label} must be a valid email`;
    }
    if (field.type === "number" && Number.isNaN(Number(value))) {
      return `${field.label} must be a number`;
    }
    if (field.type === "date" && Number.isNaN(Date.parse(value))) {
      return `${field.label} must be a valid date`;
    }
  }
  return "";
}

async function parseRecipientFile(file, fields) {
  if (!file) throw new Error("Please choose a file.");
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!SUPPORTED_EXTENSIONS.includes(extension)) {
    throw new Error("Please upload an Excel or CSV file.");
  }
  if (file.size > MAX_IMPORT_SIZE) {
    throw new Error("File is too large. Maximum size is 5 MB.");
  }

  try {
    const workbook = XLSX.read(await file.arrayBuffer(), {
      type: "array",
      cellDates: false,
    });
    const sheetName = workbook.SheetNames[0];
    if (!sheetName) throw new Error("The spreadsheet does not contain a worksheet.");
    const rows = XLSX.utils.sheet_to_json(workbook.Sheets[sheetName], {
      header: 1,
      defval: "",
      raw: false,
    });
    if (!rows.length) throw new Error("The spreadsheet is empty.");

    const headers = rows[0].map(normalizeHeader);
    const nameIndex = headers.indexOf("name");
    const emailIndex = headers.indexOf("email");
    if (nameIndex === -1 || emailIndex === -1) {
      throw new Error("File must contain 'name' and 'email' columns.");
    }

    const fieldIndexes = fields.map((field) => ({
      field,
      index: headers.indexOf(normalizeHeader(field.key)),
      labelIndex: headers.indexOf(normalizeHeader(field.label)),
    }));
    const parsedRows = rows.slice(1)
      .map((row) => ({
        name: String(row[nameIndex] ?? "").trim(),
        email: String(row[emailIndex] ?? "").trim(),
        data: Object.fromEntries(fieldIndexes.map(({ field, index, labelIndex }) => [
          field.key,
          String(row[index >= 0 ? index : labelIndex >= 0 ? labelIndex : -1] ?? "").trim(),
        ])),
      }))
      .filter((row) => row.name || row.email)
      .map((row, index) => ({
        ...row,
        rowNumber: index + 2,
        error: validateImportedRow(row, fields),
      }));
    if (!parsedRows.length) throw new Error("The spreadsheet has no recipient rows.");
    return { fileName: file.name, rows: parsedRows };
  } catch (error) {
    if (error.message.startsWith("File must") || error.message.startsWith("The spreadsheet")) {
      throw error;
    }
    throw new Error("Could not read this spreadsheet. Please make sure it is valid.");
  }
}

function App() {
  const [form, setForm] = useState(initialForm);
  const [recipients, setRecipients] = useState([
    { name: "", email: "", data: {} },
  ]);
  const [fields, setFields] = useState([]);
  const [job, setJob] = useState(null);
  const [certificates, setCertificates] = useState([]);
  const [error, setError] = useState("");
  const [submitState, setSubmitState] = useState("idle");
  const [refreshState, setRefreshState] = useState("idle");
  const [health, setHealth] = useState("checking");
  const [downloadState, setDownloadState] = useState("");
  const [resultFilter, setResultFilter] = useState("all");
  const [resultSearch, setResultSearch] = useState("");
  const [inputMode, setInputMode] = useState("manual");
  const [importPreview, setImportPreview] = useState(null);
  const [importState, setImportState] = useState("idle");

  const checkHealth = useCallback(async () => {
    try {
      await getHealth();
      setHealth("connected");
    } catch {
      setHealth("unavailable");
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  const refreshJob = useCallback(async (jobId, showLoading = true) => {
    if (showLoading) setRefreshState("loading");
    try {
      const [nextJob, nextCertificates] = await Promise.all([
        getJob(jobId),
        getCertificates(jobId),
      ]);
      setJob(nextJob);
      setCertificates(nextCertificates.items);
      setError("");
      setRefreshState("idle");
      return nextJob;
    } catch (requestError) {
      setError(requestError.message);
      setRefreshState("error");
      return null;
    }
  }, []);

  useEffect(() => {
    if (!job?.id || TERMINAL_STATES.has(job.status)) return undefined;
    const interval = window.setInterval(() => {
      refreshJob(job.id, false);
    }, 1500);
    return () => window.clearInterval(interval);
  }, [job?.id, job?.status, refreshJob]);

  const updateForm = (event) => {
    const { name, value } = event.target;
    setForm((current) => ({ ...current, [name]: value }));
  };

  const updateRecipient = (index, field, value) => {
    setRecipients((current) =>
      current.map((recipient, recipientIndex) =>
        recipientIndex === index
          ? { ...recipient, [field]: value }
          : recipient,
      ),
    );
  };

  const updateRecipientData = (index, key, value) => {
    setRecipients((current) =>
      current.map((recipient, recipientIndex) =>
        recipientIndex === index
          ? { ...recipient, data: { ...recipient.data, [key]: value } }
          : recipient,
      ),
    );
  };

  const addRecipient = () => {
    setRecipients((current) => [...current, { name: "", email: "", data: {} }]);
  };

  const removeRecipient = (index) => {
    setRecipients((current) => current.filter((_, itemIndex) => itemIndex !== index));
  };

  const submit = async (event) => {
    event.preventDefault();
    const submittedRecipients = inputMode === "upload"
      ? importPreview?.rows.map(({ name, email, data }) => ({ name, email, data })) || []
      : recipients;
    if (!submittedRecipients.length) {
      setError("Add at least one recipient before generating certificates.");
      return;
    }
    if (!form.event_name.trim() || !form.issued_by.trim()) {
      setError("Event name and issuer are required.");
      return;
    }

    setSubmitState("loading");
    setError("");
    try {
      const created = await createJob({
        certificate: form,
        fields,
        recipients: submittedRecipients,
      });
      setSubmitState("idle");
      await refreshJob(created.id);
    } catch (requestError) {
      setSubmitState("error");
      setError(requestError.message);
    }
  };

  const reset = () => {
    setJob(null);
    setCertificates([]);
    setError("");
    setForm(initialForm);
    setRecipients([{ name: "", email: "", data: {} }]);
    setFields([]);
    setInputMode("manual");
    setImportPreview(null);
    setImportState("idle");
    setResultFilter("all");
    setResultSearch("");
  };

  const handleImport = async (file) => {
    setImportState("loading");
    setError("");
    try {
      setImportPreview(await parseRecipientFile(file, fields));
      setImportState("idle");
    } catch (importError) {
      setImportPreview(null);
      setImportState("error");
      setError(importError.message);
    }
  };

  const saveBlob = async (path, key, filename) => {
    setDownloadState(key);
    setError("");
    let completed = false;
    try {
      const blob = await downloadFile(path);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setDownloadState(`${key}:downloaded`);
      window.setTimeout(() => {
        setDownloadState((current) =>
          current === `${key}:downloaded` ? "" : current,
        );
      }, 1800);
      completed = true;
    } catch (downloadError) {
      setError(downloadError.message);
    } finally {
      if (!completed) setDownloadState("");
    }
  };

  const progress = useMemo(() => {
    if (!job?.counts || !job.total) return 0;
    return Math.round(
      ((job.counts.succeeded + job.counts.failed) / job.total) * 100,
    );
  }, [job]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">C</div>
          <div>
            <div className="brand-name">CertBatcher</div>
            <div className="brand-subtitle">Certificate Generation</div>
          </div>
        </div>
        <div className={`health health-${health}`}>
          <span className="health-dot" />
          {health === "connected"
            ? "API connected"
            : health === "unavailable"
              ? "API unavailable"
              : "Checking API"}
        </div>
      </header>

      <main className="content">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Certificate operations</p>
            <h1>{job ? "Job progress" : "Create a certificate job"}</h1>
            <p className="heading-copy">
              Generate personalized certificates for multiple recipients.
            </p>
          </div>
          {job && (
            <button className="button button-secondary" onClick={reset}>
              + New Job
            </button>
          )}
        </div>

        {error && (
          <div className="alert" role="alert">
            <strong>Something needs attention.</strong>
            <span>{error}</span>
          </div>
        )}

        {!job ? (
          <form className="card form-card" onSubmit={submit}>
            <div className="section-heading">
              <div>
                <h2>Certificate details</h2>
                <p>These details will appear on every generated certificate.</p>
              </div>
              <span className="step-label">01 / 02</span>
            </div>
            <div className="field-grid">
              <label>
                Certificate title
                <input name="title" value={form.title} onChange={updateForm} />
              </label>
              <label>
                Event name <span className="required">*</span>
                <input
                  name="event_name"
                  value={form.event_name}
                  onChange={updateForm}
                  placeholder="e.g. Python Bootcamp 2026"
                  required
                />
              </label>
              <label>
                Issued by <span className="required">*</span>
                <input
                  name="issued_by"
                  value={form.issued_by}
                  onChange={updateForm}
                  placeholder="e.g. ABC Academy"
                  required
                />
              </label>
              <label>
                Issue date <span className="required">*</span>
                <input
                  name="issue_date"
                  type="date"
                  value={form.issue_date}
                  onChange={updateForm}
                  required
                />
              </label>
            </div>
            <FieldBuilder fields={fields} setFields={setFields} />

            <div className="mode-tabs" role="tablist" aria-label="Recipient input mode">
              <button
                type="button"
                className={`mode-tab ${inputMode === "manual" ? "active" : ""}`}
                onClick={() => setInputMode("manual")}
              >
                Manual entry
              </button>
              <button
                type="button"
                className={`mode-tab ${inputMode === "upload" ? "active" : ""}`}
                onClick={() => setInputMode("upload")}
              >
                Excel / CSV upload
              </button>
            </div>
            {inputMode === "upload" ? (
              <UploadPanel
                preview={importPreview}
                state={importState}
                onFile={handleImport}
                fields={fields}
              />
            ) : null}
            {inputMode === "manual" ? (
            <>
            <div className="section-heading recipient-heading">
              <div>
                <h2>Recipients</h2>
                <p>Each recipient is validated independently by the API.</p>
              </div>
              <span className="recipient-count">
                {recipients.length} {recipients.length === 1 ? "recipient" : "recipients"}
              </span>
            </div>
            <div className="recipient-table">
              <div className="table-header" style={{ gridTemplateColumns: `repeat(${fields.length + 2}, minmax(130px, 1fr)) 34px` }}>
                <span>Name</span>
                <span>Email <small>optional</small></span>
                {fields.map((field) => <span key={field.key}>{field.label}{field.required ? " *" : ""}</span>)}
                <span aria-hidden="true" />
              </div>
              {recipients.map((recipient, index) => (
                <div className="recipient-row" key={index} style={{ gridTemplateColumns: `repeat(${fields.length + 2}, minmax(130px, 1fr)) 34px` }}>
                  <input
                    aria-label={`Recipient ${index + 1} name`}
                    value={recipient.name}
                    onChange={(event) =>
                      updateRecipient(index, "name", event.target.value)
                    }
                    placeholder="Recipient name"
                  />
                  <input
                    aria-label={`Recipient ${index + 1} email`}
                    type="email"
                    value={recipient.email}
                    onChange={(event) =>
                      updateRecipient(index, "email", event.target.value)
                    }
                    placeholder="name@example.com"
                  />
                  {fields.map((field) => (
                    <input
                      key={field.key}
                      aria-label={`Recipient ${index + 1} ${field.label}`}
                      type={field.type === "number" ? "number" : field.type === "date" ? "date" : field.type === "email" ? "email" : "text"}
                      value={recipient.data?.[field.key] || ""}
                      onChange={(event) => updateRecipientData(index, field.key, event.target.value)}
                      placeholder={field.label}
                      required={field.required}
                    />
                  ))}
                  <button
                    className="icon-button"
                    type="button"
                    onClick={() => removeRecipient(index)}
                    disabled={recipients.length === 1}
                    aria-label={`Remove recipient ${index + 1}`}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            <button className="add-recipient" type="button" onClick={addRecipient}>
              <span>+</span> Add recipient
            </button>
            </>
            ) : null}
            <div className="form-footer">
              <span className="form-note">Fields marked with * are required.</span>
              <button
                className="button button-primary"
                type="submit"
                disabled={submitState === "loading"}
              >
                {submitState === "loading" ? "Creating job…" : "Generate certificates"}
                <span aria-hidden="true">→</span>
              </button>
            </div>
          </form>
        ) : (
          <JobView
            job={job}
            certificates={certificates}
            progress={progress}
            refreshState={refreshState}
            downloadState={downloadState}
            resultFilter={resultFilter}
            setResultFilter={setResultFilter}
            resultSearch={resultSearch}
            setResultSearch={setResultSearch}
            onRefresh={() => refreshJob(job.id)}
            onDownload={(certificate) =>
              saveBlob(
                certificateDownloadPath(job.id, certificate.id),
                certificate.id,
                `certificate-${certificate.id}.pdf`,
              )
            }

            onDownloadAll={() =>
              saveBlob(
                jobDownloadPath(job.id),
                "zip",
                `certificates-${job.id}.zip`,
              )
            }
          />
        )}
      </main>
      <footer className="footer">CertBatcher <span>•</span> FastAPI + React</footer>
    </div>
  );
}

function FieldBuilder({ fields, setFields }) {
  const addField = () => {
    let index = fields.length + 1;
    let key = `field_${index}`;
    while (fields.some((field) => field.key === key)) {
      index += 1;
      key = `field_${index}`;
    }
    setFields((current) => [...current, {
      key,
      label: `Custom field ${index}`,
      type: "text",
      required: false,
    }]);
  };
  const updateField = (index, key, value) => {
    setFields((current) => current.map((field, fieldIndex) =>
      fieldIndex === index ? { ...field, [key]: value } : field,
    ));
  };
  return (
    <section className="custom-fields">
      <div className="section-heading compact">
        <div><h2>Custom fields</h2><p>Optional values can be imported and printed on each certificate.</p></div>
        <button type="button" className="button button-quiet" onClick={addField} disabled={fields.length >= 20}>+ Add field</button>
      </div>
      {fields.map((field, index) => (
        <div className="custom-field-row" key={field.key}>
          <input value={field.label} onChange={(event) => updateField(index, "label", event.target.value)} placeholder="Label" aria-label="Field label" />
          <input value={field.key} onChange={(event) => updateField(index, "key", event.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_"))} placeholder="key_name" aria-label="Field key" />
          <select value={field.type} onChange={(event) => updateField(index, "type", event.target.value)} aria-label="Field type">
            <option value="text">Text</option><option value="email">Email</option><option value="number">Number</option><option value="date">Date</option>
          </select>
          <label className="checkbox-label"><input type="checkbox" checked={field.required} onChange={(event) => updateField(index, "required", event.target.checked)} /> Required</label>
          <button type="button" className="icon-button" onClick={() => setFields((current) => current.filter((_, fieldIndex) => fieldIndex !== index))} aria-label={`Remove ${field.label}`}>×</button>
        </div>
      ))}
    </section>
  );
}

function UploadPanel({ preview, state, onFile, fields }) {
  const handleInput = (event) => {
    onFile(event.target.files[0]);
    event.target.value = "";
  };
  const handleDrop = (event) => {
    event.preventDefault();
    onFile(event.dataTransfer.files[0]);
  };

  return (
    <div className="upload-section">
      <label
        className="upload-dropzone"
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".xlsx,.xls,.csv"
          onChange={handleInput}
          hidden
        />
        <span className="upload-icon">↥</span>
        <strong>{state === "loading" ? "Reading file…" : "Drop Excel or CSV here"}</strong>
        <span>or <u>choose a file</u></span>
        <small>Supported: .xlsx, .xls, .csv · Maximum 5 MB</small>
      </label>
      {preview ? (
        <div className="import-preview">
          <div className="preview-summary">
            <div>
              <strong>{preview.fileName}</strong>
              <span>{preview.rows.length} recipients · empty rows ignored</span>
            </div>
            <div className="preview-counts">
              <span className="valid-count">
                {preview.rows.filter((row) => !row.error).length} valid
              </span>
              <span className="invalid-count">
                {preview.rows.filter((row) => row.error).length} invalid
              </span>
            </div>
          </div>
          <div className="preview-table-wrap">
            <table className="preview-table">
              <thead>
                <tr><th>#</th><th>Name</th><th>Email</th>{fields.map((field) => <th key={field.key}>{field.label}</th>)}<th>Status</th></tr>
              </thead>
              <tbody>
                {preview.rows.map((row) => (
                  <tr key={row.rowNumber}>
                    <td>{row.rowNumber}</td>
                    <td>{row.name || "—"}</td>
                    <td>{row.email || "—"}</td>
                    {fields.map((field) => <td key={field.key}>{row.data?.[field.key] || "—"}</td>)}
                    <td className={row.error ? "row-invalid" : "row-valid"}>
                      {row.error ? `✕ ${row.error}` : "✓ Valid"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="upload-hint">
          Expected columns: <code>name</code>, <code>email</code>, and any configured
          custom field keys or labels. Invalid rows remain visible and are handled by the backend.
        </p>
      )}
    </div>
  );
}

function JobView({
  job,
  certificates,
  progress,
  refreshState,
  downloadState,
  resultFilter,
  setResultFilter,
  resultSearch,
  setResultSearch,
  onRefresh,
  onDownload,
  onDownloadAll,
}) {
  const isTerminal = TERMINAL_STATES.has(job.status);
  const successCount = job.counts?.succeeded || 0;
  const failedCount = job.counts?.failed || 0;
  const pendingCount = job.counts?.pending || 0;
  const processedCount = successCount + failedCount;
  const normalizedSearch = resultSearch.trim().toLowerCase();
  const filteredCertificates = certificates.filter((certificate) => {
    const matchesFilter =
      resultFilter === "all" ||
      (resultFilter === "success" && certificate.status === "SUCCESS") ||
      (resultFilter === "failed" && certificate.status === "FAILED") ||
      (resultFilter === "pending" && certificate.status === "PENDING");
    const matchesSearch =
      !normalizedSearch ||
      [
        certificate.recipient_name,
        certificate.recipient_email,
        ...Object.values(certificate.data || {}),
      ]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(normalizedSearch));
    return matchesFilter && matchesSearch;
  });

  return (
    <div className="results-stack">
      <section className="card progress-card">
        <div className="progress-topline">
          <div>
            <div className="section-heading compact">
              <div>
                <h2>Generation progress</h2>
                <p className="job-id">Job ID · {job.id}</p>
              </div>
              <StatusBadge status={job.status} />
            </div>
          </div>
          <button
            className="button button-quiet"
            onClick={onRefresh}
            disabled={refreshState === "loading"}
          >
            {refreshState === "loading" ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-meta">
          <span>{isTerminal ? "Processing complete" : "Generating certificates…"}</span>
          <strong>{progress}%</strong>
        </div>
        <div className="processed-label">
          {processedCount} of {job.total} processed
        </div>
        <div className="metric-grid">
          <Metric label="Total" value={job.total} />
          <Metric label="Successful" value={job.counts?.succeeded} tone="success" />
          <Metric label="Failed" value={job.counts?.failed} tone="danger" />
          <Metric label="Pending" value={job.counts?.pending} tone="pending" />
        </div>
        <SummaryBanner job={job} successCount={successCount} failedCount={failedCount} />
        <JobTimeline job={job} />
      </section>

      <section className="card certificates-card">
        <div className="section-heading">
          <div>
            <h2>Certificate results</h2>
            <p>Results stay in the same order as your submitted recipients.</p>
          </div>
          {successCount > 0 && (
            <button
              className="button button-primary"
              onClick={onDownloadAll}
              disabled={downloadState === "zip"}
            >
              {downloadState === "zip"
                ? "Preparing ZIP…"
                : downloadState === "zip:downloaded"
                  ? "Downloaded"
                  : "Download all"}
              <span aria-hidden="true">↓</span>
            </button>
          )}
        </div>
        <div className="results-controls">
          <div className="filter-group" role="group" aria-label="Certificate result filter">
            <FilterButton
              active={resultFilter === "all"}
              onClick={() => setResultFilter("all")}
              label={`All (${certificates.length})`}
            />
            <FilterButton
              active={resultFilter === "success"}
              onClick={() => setResultFilter("success")}
              label={`Successful (${successCount})`}
            />
            <FilterButton
              active={resultFilter === "failed"}
              onClick={() => setResultFilter("failed")}
              label={`Failed (${failedCount})`}
            />
            {pendingCount > 0 && (
              <FilterButton
                active={resultFilter === "pending"}
                onClick={() => setResultFilter("pending")}
                label={`Pending (${pendingCount})`}
              />
            )}
          </div>
          <input
            className="search-input"
            type="search"
            placeholder="Search recipients…"
            aria-label="Search recipients"
            value={resultSearch}
            onChange={(event) => setResultSearch(event.target.value)}
          />
        </div>
        {filteredCertificates.length ? (
          <div className="results-table-wrap">
            <table className="results-table">
              <thead>
                <tr>
                  <th>Recipient</th>
                  <th>Email</th>
                  {job.fields?.map((field) => <th key={field.key}>{field.label}</th>)}
                  <th>Status</th>
                  <th>Details</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filteredCertificates.map((certificate) => (
                  <tr key={certificate.id}>
                    <td className="name-cell">{certificate.recipient_name || "Unnamed recipient"}</td>
                    <td>{certificate.recipient_email || "—"}</td>
                    {job.fields?.map((field) => (
                      <td key={field.key}>{certificate.data?.[field.key] ?? "—"}</td>
                    ))}
                    <td><StatusBadge status={certificate.status} /></td>
                    <td className="detail-cell">
                      {certificate.error_message || (certificate.status === "SUCCESS" ? "Ready to download" : "Waiting to process")}
                    </td>
                    <td className="action-cell">
                      {certificate.status === "SUCCESS" && (
                        <button
                          className="download-link"
                          onClick={() => onDownload(certificate)}
                          disabled={downloadState === certificate.id || downloadState === `${certificate.id}:downloaded`}
                        >
                          {downloadState === certificate.id
                            ? "Downloading…"
                            : downloadState === `${certificate.id}:downloaded`
                              ? "Downloaded"
                              : "Download PDF"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">
            {certificates.length
              ? `No ${resultSearch ? "matching " : ""}${resultFilter === "all" ? "" : resultFilter} certificates.`
              : "No certificates available yet."}
          </div>
        )}
      </section>
    </div>
  );
}

function FilterButton({ active, onClick, label }) {
  return (
    <button
      className={`filter-button ${active ? "active" : ""}`}
      onClick={onClick}
      type="button"
      aria-pressed={active}
    >
      {label}
    </button>
  );
}

function SummaryBanner({ job, successCount, failedCount }) {
  if (job.status === "COMPLETED") {
    return (
      <div className="summary-banner summary-success">
        <span className="summary-icon">✓</span>
        <div><strong>All certificates generated</strong><span>{successCount} certificates generated successfully.</span></div>
      </div>
    );
  }
  if (job.status === "COMPLETED_WITH_ERRORS") {
    return (
      <div className="summary-banner summary-warning">
        <span className="summary-icon">!</span>
        <div><strong>Completed with errors</strong><span>{successCount} generated successfully · {failedCount} failed.</span></div>
      </div>
    );
  }
  if (job.status === "FAILED") {
    return (
      <div className="summary-banner summary-danger">
        <span className="summary-icon">×</span>
        <div><strong>Certificate generation failed</strong><span>{job.error || "Unable to process the certificate job."}</span></div>
      </div>
    );
  }
  return null;
}

function JobTimeline({ job }) {
  const timestamps = [
    ["Created", job.created_at],
    ["Started", job.started_at],
    ["Completed", job.finished_at],
  ];
  return (
    <div className="job-timeline">
      {timestamps.map(([label, timestamp]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>{timestamp ? new Date(timestamp).toLocaleString() : "—"}</strong>
        </div>
      ))}
    </div>
  );
}

function Metric({ label, value, tone = "" }) {
  return (
    <div className="metric">
      <span className={`metric-value ${tone}`}>{value ?? 0}</span>
      <span className="metric-label">{label}</span>
    </div>
  );
}

function StatusBadge({ status }) {
  return <span className={`status-badge status-${status.toLowerCase()}`}>{status}</span>;
}

export default App;
