import { API_BASE_URL } from "./config.js";

/**
 * Small fetch wrapper: joins the base URL, parses JSON safely and
 * converts failures into friendly, non-technical error messages.
 */
async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw new Error("We could not reach the FarmSense service. Please check that it is running, then try again.");
  }

  let data = null;
  try {
    data = await res.json();
  } catch {
    // No JSON body — that's fine.
  }

  if (!res.ok) {
    const msg = data && (data.detail || data.message || data.error);
    throw new Error(typeof msg === "string" && msg ? msg : "Something went wrong. Please try again.");
  }
  return data;
}

export const api = {
  // 1. Create farmer profile
  postProfile: (body) =>
    request("/farmer/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // 2a. Upload crop photo (multipart, field name MUST be "photo")
  uploadPhoto: (farmerId, file) => {
    const fd = new FormData();
    fd.append("photo", file);
    return request(`/farmer/${farmerId}/photo`, { method: "POST", body: fd });
  },

  // 2b. Manual leaf condition fallback
  postLeafCondition: (farmerId, condition) =>
    request(`/farmer/${farmerId}/leaf-condition`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ condition }),
    }),

  // 3. Main recommendation
  getRecommendation: (farmerId) => request(`/farmer/${farmerId}/recommendation`),

  // 3b. Send advice over SMS
  sendSms: (farmerId) => request(`/farmer/${farmerId}/sms`, { method: "POST" }),

  // 4. History + soil moisture trend
  getHistory: (farmerId) => request(`/farmer/${farmerId}/history`),

  // 5. Environment summary
  getEnvironment: (farmerId) => request(`/farmer/${farmerId}/environment`),
};

/** Pull the farmer id out of whatever shape the backend returns. */
export function extractFarmerId(data) {
  if (data == null) return null;
  const id = data.farmer_id ?? data.id ?? data.farmerId;
  return id == null ? null : String(id);
}
