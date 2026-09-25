import { useRef, useState } from "react";
import { api } from "../api.js";
import { CameraIcon, ConfidenceBar, LoadingCard, LeafIcon } from "../components/ui.jsx";

const CONDITION_OPTIONS = [
  { value: "normal", label: "Normal", desc: "Looks healthy", icon: "healthy" },
  { value: "spotted", label: "Spotted leaves", desc: "Spots on leaves", icon: "spotted" },
  { value: "yellowing", label: "Yellowing", desc: "Leaves turning yellow", icon: "yellow" },
  { value: "wilting", label: "Wilting", desc: "Droopy or dry", icon: "wilting" },
];

const FRIENDLY = {
  normal: "Your crop looks healthy.",
  healthy: "Your crop looks healthy.",
  spotted: "We can see spots on the leaves.",
  yellowing: "The leaves are turning yellow.",
  wilting: "The crop looks wilted and droopy.",
};

function friendlyCondition(data) {
  if (!data) return "";
  const key = String(data.condition ?? data.leaf_condition ?? "").toLowerCase();
  if (FRIENDLY[key]) return FRIENDLY[key];
  if (data.message) return String(data.message);
  return key ? `We noted: ${key.replace(/_/g, " ")}.` : "We saved your crop check.";
}

function confidenceOf(data) {
  const v = data?.confidence_pct ?? data?.confidence ?? data?.confidence_score;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function PhotoUpload({ farmerId, onDone }) {
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [highlightFallback, setHighlightFallback] = useState(false);
  const [conditionBusy, setConditionBusy] = useState(null);
  const [conditionError, setConditionError] = useState("");
  const [result, setResult] = useState(null);
  const resultRef = useRef(null);

  const showResult = (data) => {
    setResult(data);
    setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }), 80);
  };

  const pickFile = () => fileRef.current?.click();

  const onFileChange = (e) => {
    const f = e.target.files?.[0];
    setUploadError("");
    setHighlightFallback(false);
    setResult(null);
    if (f) {
      setFile(f);
      setPreview(URL.createObjectURL(f));
    }
  };

  const clearPhoto = () => {
    setFile(null);
    setPreview(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setUploadError("");
    try {
      const data = await api.uploadPhoto(farmerId, file);
      showResult(data);
    } catch (err) {
      // Photo failed — never a dead end: surface the manual fallback clearly.
      setUploadError(
        (err.message || "We could not check the photo.") + " You can describe your crop below instead."
      );
      setHighlightFallback(true);
    } finally {
      setUploading(false);
    }
  };

  const chooseCondition = async (value) => {
    setConditionBusy(value);
    setConditionError("");
    setUploadError("");
    try {
      const data = await api.postLeafCondition(farmerId, value);
      showResult(data);
    } catch (err) {
      setConditionError(err.message || "That did not go through. Please try again.");
    } finally {
      setConditionBusy(null);
    }
  };

  if (uploading) return <LoadingCard label="Checking your crop photo…" />;

  return (
    <div className="screen">
      <div className="glass card intro-card">
        <h1>How is your crop doing?</h1>
        <p className="muted">Share a photo of your crop, or simply tell us what you see.</p>
      </div>

      <div className="glass card">
        {preview ? (
          <div className="preview-wrap">
            <img src={preview} alt="Your crop" className="preview-img" />
          </div>
        ) : (
          <button type="button" className="upload-zone" onClick={pickFile}>
            <CameraIcon size={44} />
            <span className="uz-title">Tap to add a photo</span>
            <span className="uz-sub">A close-up of the leaves works best</span>
          </button>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          onChange={onFileChange}
          style={{ display: "none" }}
          aria-hidden="true"
          tabIndex={-1}
        />

        {preview && (
          <div className="btn-stack">
            <button type="button" className="btn btn-primary" onClick={upload} disabled={uploading}>
              Check my crop
            </button>
            <button type="button" className="btn btn-ghost" onClick={clearPhoto}>
              Choose a different photo
            </button>
          </div>
        )}

        {uploadError && (
          <p className="error-text" role="alert">
            {uploadError}
          </p>
        )}
      </div>

      <div className={`glass card ${highlightFallback ? "highlight" : ""}`}>
        <h2 className="card-title">Skip photo — describe your crop instead</h2>
        <p className="muted">Look at your crop and tap what you see:</p>
        <div className="option-grid">
          {CONDITION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className="option-btn"
              onClick={() => chooseCondition(opt.value)}
              disabled={conditionBusy !== null}
            >
              <span className={`cond-dot cond-${opt.icon}`} />
              <span className="option-label">{opt.label}</span>
              <span className="option-desc">{opt.desc}</span>
            </button>
          ))}
        </div>
        {conditionError && (
          <p className="error-text" role="alert">
            {conditionError}
          </p>
        )}
      </div>

      {result && (
        <div className="glass card result-card" ref={resultRef}>
          <span className="result-check">
            <LeafIcon size={30} />
          </span>
          <p className="result-text">{friendlyCondition(result)}</p>
          {confidenceOf(result) !== null && (
            <div className="confidence-inline">
              <ConfidenceBar value={confidenceOf(result)} />
              <span className="confidence-num">{Math.round(confidenceOf(result))}% sure</span>
            </div>
          )}
        </div>
      )}

      <button type="button" className="btn btn-primary btn-big" onClick={onDone}>
        See my advice
      </button>
    </div>
  );
}
