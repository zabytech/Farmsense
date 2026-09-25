# 🌾 FarmSense

Live Video Demo -> https://drive.google.com/file/d/1PVLH4cIJxnNWEMyuhtp5CakAInwSt38G/view?usp=sharing

### Build the Decision, Not the Dashboard.

> **FarmSense is an intelligent decision-support system for smallholder farmers that combines weather, modeled soil conditions, crop information, farmer history, and crop-health signals to produce one clear, explainable action.**

Farmers already have access to large amounts of agricultural information. The problem is not always the lack of data. The problem is:

> **What should the farmer actually do with all this information?**

FarmSense is built around that question. Instead of simply displaying weather forecasts, soil values, crop information, or disease predictions, FarmSense combines these signals and produces a **specific, explainable recommendation**:

- What should the farmer do?
- When should they do it?
- Why is the system recommending it?
- How confident is the system?
- What could happen if the farmer ignores it?

---

## 🏆 Project Information

| Category | Details |
|---|---|
| **Project** | FarmSense |
| **Team** | Code Crusaders |
| **Team Lead** | Danish |
| **Members** | Shreyas, Zabi, Subhash |
| **Event** | Innovators Conclave 2026 |
| **Track** | PS-01 — Track 06 AgriTech |
| **Project Type** | AI-powered Agricultural Decision Support System |
| **Current Stage** | Hackathon Prototype / MVP |

---

## 📌 Table of Contents

- [Problem](#-problem)
- [Our Solution](#-our-solution)
- [Core Idea](#-core-idea)
- [How FarmSense Works](#-how-farmsense-works)
- [Complete Data Flow](#-complete-data-flow)
- [System Architecture](#-system-architecture)
- [Why Rule-Based Decision Making](#-why-rule-based-decision-making)
- [Role of the LLM](#-role-of-the-llm)
- [Recommendation Delivery](#-recommendation-delivery)
- [Mock Mode and Fallbacks](#-mock-mode-and-fallbacks)
- [Crop Support](#-crop-support)
- [Technology Stack](#️-technology-stack)
- [Repository Structure](#-repository-structure)
- [Installation](#-installation)
- [Environment Variables](#-environment-variables)
- [Testing](#-testing)
- [API Documentation](#-api-documentation)
- [Example Decision](#-example-decision)
- [Design Principles](#️-design-principles)
- [Security Considerations](#-security-considerations)
- [Current Limitations](#️-current-limitations)
- [Future Scope](#-future-scope)
- [Scalability](#-scalability)
- [Team](#-team-code-crusaders)

---

## 🌱 Problem

Smallholder farmers make several important decisions every day:

- When should I irrigate?
- Is my crop receiving enough water?
- Should I apply fertilizer?
- Is my crop showing signs of disease?
- Will upcoming weather affect my crop?
- Should I act now or wait?

The information needed already exists across multiple sources — weather forecasts, historical weather, soil information, crop growth stage, watering history, fertilizer history, and crop health signals. However, these signals are often disconnected. A weather app tells the farmer rain is expected. A soil dashboard shows soil moisture. A crop-health model flags a possible disease. But the farmer still has to connect these pieces and decide:

> **"What should I do next?"**

That is the gap FarmSense addresses.

---

## 💡 Our Solution

FarmSense acts as a decision layer between agricultural data and the farmer. Instead of only showing information, it combines available signals and produces an actionable recommendation.

```
Farmer Data
     ↓
Weather / Soil Data
     ↓
Crop Health Data
     ↓
Growth Stage Calculation
     ↓
Rule-Based Decision Engine
     ↓
Priority Scoring
     ↓
Final Agricultural Action
     ↓
LLM Language Layer
     ↓
Farmer-Friendly Recommendation
     ↓
App / SMS
```

**The most important architectural principle:**

> **The decision engine decides. The LLM explains.**

---

## 🎯 Core Idea

Traditional systems answer *"What is the weather?"* or *"What is the soil moisture?"*. FarmSense answers the next question:

> **"Considering all these factors, what should this specific farmer do next?"**

The system focuses on **Action → Time → Reason → Confidence → Consequence**, rather than simply displaying raw data.

---

## 🧑‍🌾 How FarmSense Works

### 1. Farmer Profile
The farmer provides farm and crop details — Farmer ID, location, crop type, planting date, crop height, watering frequency, irrigation type, watering/fertilizer history, and an optional leaf photo or manual symptom report.

```
Farmer ID: FARM-102
Location: Bengaluru
Crop: Tomato
Planting Date: 2026-08-10
Crop Height: 48 cm
Irrigation: Drip
Watering Frequency: Every 2 days
Fertilizer: Applied recently
```

### 2. Environmental Data
FarmSense uses the farmer's location to retrieve current conditions, short-term forecast, and historical weather from public sources. Soil moisture is currently a **modeled/estimated value**, not a physical sensor reading — no IoT hardware is required for this prototype.

### 3. Crop Growth Stage
Crop age alone isn't enough — the same conditions affect a crop differently at different stages.

```
Crop Type + Planting Date + Crop-Specific Rules → Growth Stage
                                                   (Vegetative / Flowering / Fruiting)
```

### 4. Crop Health Assessment
- **Option A — Image-based:** Leaf/crop photo → pretrained vision model → disease/pest/healthy signal.
- **Option B — Manual reporting:** Farmer reports symptoms (Normal / Spotted / Yellowing / Wilting) when no image is available.

### 5. Decision Engine
The core of FarmSense. It combines soil moisture trend, weather forecast, temperature, humidity, growth stage, watering/fertilizer history, crop condition, and pest/disease results — then scores three decision areas:

```
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│  IRRIGATION  │   │  FERTILIZER  │   │  PEST / DISEASE   │
└──────────────┘   └──────────────┘   └──────────────────┘
```

Each area gets an urgency/priority score; the highest-priority actionable recommendation is selected.

**Example scoring:**
```
Falling soil moisture + High temperature + No rain forecast + Flowering stage
        ↓
Higher irrigation urgency → Irrigation recommendation
```

### Explainability
Every recommendation carries five parts:

| Field | Answers |
|---|---|
| **Action** | What should the farmer do? |
| **Time Window** | When should they do it? |
| **Confidence** | How strongly do signals support this? |
| **Reasoning** | Which factors triggered it? |
| **Consequence** | What happens if ignored? |

---

## 🔄 Complete Data Flow

```
                    FARMER
                       │
                       ▼
              ┌─────────────────┐
              │ Farmer Profile  │
              └────────┬────────┘
                       ▼
       ┌───────────────────────────────┐
       │      External Data Layer      │
       │  Weather · History · Soil     │
       └───────────────┬───────────────┘
                       ▼
              ┌─────────────────┐
              │ Crop Condition  │
              │ (Image/Manual)  │
              └────────┬────────┘
                       ▼
             ┌────────────────────┐
             │ Growth Stage Logic │
             └─────────┬──────────┘
                       ▼
             ┌────────────────────┐
             │  Decision Engine   │
             │ Irrigation/Fert/   │
             │ Disease Scores     │
             └─────────┬──────────┘
                       ▼
             ┌────────────────────┐
             │  Final Decision    │
             │ Action/Time/Conf/  │
             │ Reason/Consequence │
             └─────────┬──────────┘
                       ▼
               ┌──────────────┐
               │     LLM      │
               │ Language Only│
               └──────┬───────┘
                      ▼
            ┌─────────────────────┐
            │ Farmer-Friendly     │
            │ Recommendation      │
            └─────────┬───────────┘
                ┌─────┴─────┐
                ▼           ▼
              WEB          SMS
```

---

## 🏗️ System Architecture

FarmSense is split into two independently organized applications:

```
farmsense/
├── farmsense-backend/     → Data processing, decision engine, crop rules,
│                            crop-health processing, LLM + SMS integration, REST APIs
└── farmsense-frontend/    → Farmer interface, profile collection, recommendation
                             display, history/trends, image upload
```

---

## 🤖 Why Rule-Based Decision Making?

FarmSense intentionally uses a **deterministic, rule-based engine** for its core agricultural decisions — because explainability matters when the recommendation has real consequences.

```
Soil moisture falling + High temperature + No rain forecast + Flowering stage
        ↓
Irrigation urgency increased
```

This makes the system easy to **understand, debug, audit, validate, and modify** — the same inputs always produce the same decision. This is deliberately different from letting a generative model invent agricultural advice on its own.

---

## 🤖 Role of the LLM

The LLM is completely separated from the decision layer.

**The LLM does NOT decide:**
- Whether irrigation/fertilizer is necessary
- Which action has the highest priority
- The confidence score, reasoning, or consequence

```
Rule Engine → Finalized Decision → LLM → Simple Language
```

**Example — Decision Engine Output:**
```json
{
  "action": "Irrigate",
  "time_window": "Within 6 hours",
  "confidence": 82,
  "reason": [
    "Soil moisture is falling",
    "Temperature is high",
    "No significant rain is forecast",
    "Crop is in flowering stage"
  ]
}
```

**LLM Output (language only, decision unchanged):**
> "Your crop needs water within the next 6 hours because the soil moisture is falling and no significant rain is expected. Since the crop is flowering, avoiding water stress is especially important."

---

## 📱 Recommendation Delivery

| Channel | Purpose |
|---|---|
| **🌐 Web** | Full recommendation, reasoning, confidence, crop & history info |
| **💬 SMS** | Low-bandwidth delivery for basic phones |
| **📞 Voice / IVR** | Future scope — accessibility layer for spoken recommendations |

**SMS Example:**
```
FarmSense:
Your tomato crop needs irrigation tomorrow morning.

Reason: Soil moisture is low and no significant rain is expected.
Confidence: 82%
```

The decision engine stays independent of the delivery channel — same decision, multiple channels.

---

## 🧪 Mock Mode and Fallbacks

External APIs can fail — missing keys, network issues, rate limits, downtime. FarmSense degrades gracefully instead of breaking the whole pipeline:

```
External Service → Available? ──Yes──→ Live Data ──┐
                          │                          ├──→ Decision Engine → Recommendation
                          └───No───→ Mock Data ──────┘
```

This is especially useful for local development, testing, and hackathon demos.

---

## 🌾 Crop Support

FarmSense uses **crop-specific rules** instead of one universal threshold:

| Crop | Characteristic |
|---|---|
| **Rice** | Water-intensive, distinct irrigation logic |
| **Wheat** | Staple grain, different water profile |
| **Cotton** | Long-duration, different sensitivity |
| **Tomato** | Water- & disease-sensitive, stage-dependent |
| **Maize** | Fast-growing, compressed growth stages |

**Adding a new crop** just means extending the rule set (growth stages, water sensitivity, moisture thresholds, fertilizer timing, temperature sensitivity, disease rules) — not redesigning the system.

---

## ⚙️ Technology Stack

| Layer | Tech |
|---|---|
| **Backend** | Python, FastAPI, REST APIs, Rule-based Decision Engine |
| **Frontend** | React, JavaScript, HTML, CSS |
| **AI/ML** | Pretrained plant disease/pest classifier, LLM for language generation |
| **Data** | Weather APIs, public environmental/soil data, farmer input |
| **Communication** | SMS integration (Twilio), Voice/IVR (future) |
| **Tooling** | Git, GitHub, VS Code |

---

## 📁 Repository Structure

```
farmsense/
├── farmsense-backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── rules.json
│   ├── decision_engine/
│   ├── services/
│   ├── weather_service.py
│   ├── sms_service.py
│   ├── test_smoke.py
│   └── README.md
│
├── farmsense-frontend/
│   ├── package.json
│   ├── src/
│   │   ├── config.js
│   │   └── ...
│   ├── public/
│   └── README.md
│
└── README.md
```

---

## 🚀 Installation

### Prerequisites
- Python 3.x
- Node.js & npm
- Git

### 🔧 Backend Setup
```bash
cd farmsense-backend

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (Linux/macOS)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create env file
cp .env.example .env      # Linux/macOS
copy .env.example .env    # Windows

# Run backend
uvicorn main:app --host 0.0.0.0 --port 8000
```
Backend runs at: `http://localhost:8000`

### 💻 Frontend Setup
```bash
cd farmsense-frontend
npm install
npm run dev
```
Frontend runs at: `http://localhost:5173`  
Backend URL is configured in `src/config.js`

---

## 🔐 Environment Variables

Create `farmsense-backend/.env`:

```env
# Weather
WEATHER_API_KEY=

# LLM
LLM_API_KEY=

# Twilio / SMS
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
```

> ⚠️ **Never commit** `.env`, API keys, tokens, or passwords to GitHub. Use `.env.example` to document required configuration.

---

## 🧪 Testing

```bash
python test_smoke.py
```

**Pre-demo validation checklist:**
1. Start backend
2. Check API health
3. Start frontend
4. Submit farmer profile
5. Verify weather/environment data
6. Verify crop growth stage
7. Verify decision engine output
8. Verify recommendation
9. Verify LLM phrasing
10. Verify SMS (if enabled)

---

## 📚 API Documentation

Once running, interactive docs are available at:
```
http://localhost:8000/docs
```

**Request flow:**
```
Frontend → FastAPI Endpoint → Data Validation → Services → Decision Engine → Recommendation → Frontend
```

---

## 🧠 Example Decision

**Input:**
```
Crop: Tomato
Growth Stage: Flowering
Soil Moisture: Falling
Temperature: High
Rain Forecast: None significant
Last Watering: 3 days ago
```

**Output:**
```
Action: Irrigate within 6 hours
Confidence: 82%
Reason: Soil moisture is falling, temperatures are high, and no significant
        rain is forecast. Crop is in a water-sensitive flowering stage.
Consequence: Skipping irrigation may result in visible crop stress.
```

---

## 🛡️ Design Principles

1. **Decision First** — answer "what should I do?", not just "what's happening?"
2. **Explainability** — every recommendation has identifiable contributing factors
3. **Deterministic Core** — decisions come from explicit rules
4. **LLM Separation** — LLM improves communication, never controls the decision
5. **Graceful Failure** — one external service failing shouldn't break the app
6. **Channel Independence** — same recommendation across Web/SMS/Voice
7. **Extensible Rules** — new crops/regions/languages without redesign

---

## 🔒 Security Considerations

- Keep API credentials in environment variables
- Never commit `.env` files
- Validate API inputs and uploaded files
- Restrict production CORS configuration
- Use HTTPS in production
- Apply authentication for protected endpoints
- Avoid exposing internal API keys to the frontend
- Limit access to farmer data; sanitize external data

> The hackathon prototype is **not** production-hardened without the above.

---

## ⚠️ Current Limitations

| # | Limitation |
|---|---|
| 1 | Modeled (not sensor-measured) soil information |
| 2 | Limited crop coverage (defined crop set) |
| 3 | Recommendation quality depends on rule/threshold quality |
| 4 | Crop-health detection depends on pretrained model limits |
| 5 | External APIs (weather/LLM/SMS) can fail or rate-limit |
| 6 | Conversational voice agent not part of core MVP |
| 7 | No irrigation infrastructure upgrade recommendations |

---

## 🔮 Future Scope

- 🗣️ **Conversational Voice Agent** — farmers call in and ask questions like *"Should I water my crop today?"*
- 🌍 **Multilingual Recommendations** — Kannada, Hindi, Telugu, Tamil, Marathi, Bengali, etc.
- 📡 **IoT Integration** — real soil moisture, temperature, humidity, rainfall sensors
- 🛰️ **Satellite & Remote Sensing** — vegetation health, crop stress, large-scale monitoring
- 💧 **Irrigation Optimization** — method, frequency, water quantity, infrastructure upgrades
- 🧠 **Advanced ML** — models complementing the deterministic rule layer
- 📈 **Continuous Learning** — feedback loop from recommendation → farmer action → crop outcome → rule improvement

---

## 📈 Scalability

| Dimension | How it Scales |
|---|---|
| **Software** | APIs + Farmer Input + Rule Engine + AI Services — no mandatory hardware |
| **Crop** | New crops added by extending rules |
| **Regional** | Rules adapted per region/conditions |
| **Language** | Language layer extends independently of decision logic |
| **Channel** | Same recommendation via Web / SMS / Voice |

---

## 🆚 FarmSense vs Traditional Tools

| Traditional | FarmSense |
|---|---|
| Weather → Forecast | Weather + Crop + Growth Stage + History + Soil → **Action** |
| Sensor Data → Raw Measurements | Environmental Data + Crop Context + Farmer History → **Explainable Recommendation** |
| Regional Conditions → General Advice | Specific Farmer + Crop + Stage + Conditions → **Personalized Recommendation** |

---

## 👥 Team Code Crusaders

| Member | Role |
|---|---|
| **Danish** | Team Lead |
| **Shreyas** | Team Member |
| **Zabi** | Team Member |
| **Subhash** | Team Member |

**Event:** Innovators Conclave 2026  
**Track:** PS-01 | Track 06 — AgriTech

---

<div align="center">

### 🚀 FarmSense
**Build the Decision, Not the Dashboard.**

*From scattered agricultural data to one clear, explainable action.*

**FarmSense — Existing tools inform. FarmSense decides — and explains.**

</div>
