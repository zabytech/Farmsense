import { useRef, useState } from "react";
import { api, extractFarmerId } from "../api.js";

const CROPS = ["Rice", "Wheat", "Cotton", "Tomato", "Maize"];
const IRRIGATION_TYPES = ["Drip", "Sprinkler", "Flood", "Manual"];

const INITIAL = {
  lat: "",
  lng: "",
  crop_type: "",
  planting_date: "",
  crop_height_cm: "",
  watering_days_per_week: "",
  irrigation_type: "",
  avg_watering_minutes: "",
  fertilizer_used: false,
  fertilizer_amount: "",
};

export default function Onboarding({ onCreated }) {
  const [form, setForm] = useState(INITIAL);
  const [formError, setFormError] = useState("");
  const [geoMsg, setGeoMsg] = useState("");
  const [locating, setLocating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [apiError, setApiError] = useState("");
  const resultRef = useRef(null);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setGeoMsg("Location is not available on this device — you can type it in below.");
      return;
    }
    setLocating(true);
    setGeoMsg("Finding your farm…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        set("lat", Number(pos.coords.latitude.toFixed(4)));
        set("lng", Number(pos.coords.longitude.toFixed(4)));
        setLocating(false);
        setGeoMsg("Location found from your device.");
      },
      () => {
        setLocating(false);
        setGeoMsg("We could not get your location — you can type it in below.");
      },
      { timeout: 8000, maximumAge: 60000 }
    );
  };

  const validate = () => {
    const lat = parseFloat(form.lat);
    const lng = parseFloat(form.lng);
    if (Number.isNaN(lat) || Number.isNaN(lng)) return "Please tell us where your farm is.";
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return "That location does not look right — please check it.";
    if (!form.crop_type) return "Please choose your crop.";
    if (!form.planting_date) return "Please pick the day you planted.";
    if (form.crop_height_cm === "" || Number(form.crop_height_cm) < 0) return "Please enter how tall your crop is.";
    const days = Number(form.watering_days_per_week);
    if (form.watering_days_per_week === "" || Number.isNaN(days) || days < 0 || days > 7)
      return "Watering days must be between 0 and 7.";
    if (!form.irrigation_type) return "Please choose how you water your crop.";
    if (form.avg_watering_minutes === "" || Number(form.avg_watering_minutes) < 0)
      return "Please enter how long you usually water.";
    if (form.fertilizer_used && !form.fertilizer_amount.trim()) return "Please tell us how much fertilizer you used.";
    return "";
  };

  const submit = async (e) => {
    e.preventDefault();
    setApiError("");
    const problem = validate();
    setFormError(problem);
    if (problem) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    setBusy(true);
    try {
      const data = await api.postProfile({
        location: { lat: Number(form.lat), lng: Number(form.lng) },
        crop_type: form.crop_type,
        planting_date: form.planting_date,
        crop_height_cm: Number(form.crop_height_cm),
        watering_days_per_week: Number(form.watering_days_per_week),
        irrigation_type: form.irrigation_type,
        avg_watering_minutes: Number(form.avg_watering_minutes),
        fertilizer_used: form.fertilizer_used,
        fertilizer_amount: form.fertilizer_used ? form.fertilizer_amount.trim() : "",
      });
      const id = extractFarmerId(data);
      if (!id) throw new Error("The service did not send back a farmer id. Please try again.");
      onCreated(id);
    } catch (err) {
      setApiError(err.message);
      resultRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="screen" onSubmit={submit} noValidate>
      <div className="glass card intro-card">
        <h1>Welcome to your farm advisor</h1>
        <p className="muted">
          Answer a few simple questions about your farm. We use this to give you clear, personalised advice.
        </p>
      </div>

      {formError && (
        <div className="glass card form-error" role="alert">
          {formError}
        </div>
      )}

      <div className="glass card">
        <div className="field">
          <label htmlFor="lat">Where is your farm?</label>
          <button type="button" className="btn btn-secondary locate-btn" onClick={useMyLocation} disabled={locating}>
            {locating ? <span className="mini-spinner" /> : null}
            {locating ? "Finding your farm…" : "Use my location"}
          </button>
          {geoMsg && <p className="hint">{geoMsg}</p>}
          <div className="grid-2">
            <div>
              <label htmlFor="lat">Latitude</label>
              <input
                id="lat"
                className="input"
                type="number"
                step="any"
                inputMode="decimal"
                value={form.lat}
                onChange={(e) => set("lat", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="lng">Longitude</label>
              <input
                id="lng"
                className="input"
                type="number"
                step="any"
                inputMode="decimal"
                value={form.lng}
                onChange={(e) => set("lng", e.target.value)}
              />
            </div>
          </div>
          <p className="hint">Tip: tap the button, or type the numbers yourself.</p>
        </div>

        <div className="field">
          <label htmlFor="crop">What are you growing?</label>
          <select
            id="crop"
            className="input select"
            value={form.crop_type}
            onChange={(e) => set("crop_type", e.target.value)}
          >
            <option value="" disabled>
              Choose your crop
            </option>
            {CROPS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="planting_date">When did you plant it?</label>
          <input
            id="planting_date"
            className="input"
            type="date"
            value={form.planting_date}
            onChange={(e) => set("planting_date", e.target.value)}
          />
        </div>

        <div className="grid-2">
          <div className="field">
            <label htmlFor="height">How tall is it? (cm)</label>
            <input
              id="height"
              className="input"
              type="number"
              min="0"
              inputMode="numeric"
              placeholder="e.g. 45"
              value={form.crop_height_cm}
              onChange={(e) => set("crop_height_cm", e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="days">Watering days per week</label>
            <input
              id="days"
              className="input"
              type="number"
              min="0"
              max="7"
              inputMode="numeric"
              placeholder="0 – 7"
              value={form.watering_days_per_week}
              onChange={(e) => set("watering_days_per_week", e.target.value)}
            />
          </div>
        </div>

        <div className="field">
          <label htmlFor="irrigation">How do you water your crop?</label>
          <select
            id="irrigation"
            className="input select"
            value={form.irrigation_type}
            onChange={(e) => set("irrigation_type", e.target.value)}
          >
            <option value="" disabled>
              Choose watering method
            </option>
            {IRRIGATION_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="minutes">How many minutes each time?</label>
          <input
            id="minutes"
            className="input"
            type="number"
            min="0"
            inputMode="numeric"
            placeholder="e.g. 20"
            value={form.avg_watering_minutes}
            onChange={(e) => set("avg_watering_minutes", e.target.value)}
          />
        </div>

        <div className="field">
          <label>Do you use fertilizer?</label>
          <div className="segmented" role="group" aria-label="Fertilizer used">
            <button
              type="button"
              className={`seg ${form.fertilizer_used ? "active" : ""}`}
              onClick={() => set("fertilizer_used", true)}
              aria-pressed={form.fertilizer_used}
            >
              Yes
            </button>
            <button
              type="button"
              className={`seg ${!form.fertilizer_used ? "active" : ""}`}
              onClick={() => {
                set("fertilizer_used", false);
                set("fertilizer_amount", "");
              }}
              aria-pressed={!form.fertilizer_used}
            >
              No
            </button>
          </div>
        </div>

        {form.fertilizer_used && (
          <div className="field fade-slide">
            <label htmlFor="fert_amount">How much fertilizer did you use?</label>
            <input
              id="fert_amount"
              className="input"
              type="text"
              placeholder="e.g. 1 bag of urea per acre"
              value={form.fertilizer_amount}
              onChange={(e) => set("fertilizer_amount", e.target.value)}
            />
          </div>
        )}
      </div>

      <div ref={resultRef}>
        {apiError && (
          <div className="glass card form-error" role="alert">
            {apiError}
          </div>
        )}
      </div>

      <button type="submit" className="btn btn-primary btn-big" disabled={busy}>
        {busy ? "Saving…" : "Continue"}
      </button>
    </form>
  );
}
