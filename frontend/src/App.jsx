import { useState } from "react";
import Background from "./components/Background.jsx";
import Onboarding from "./screens/Onboarding.jsx";
import PhotoUpload from "./screens/PhotoUpload.jsx";
import Recommendation from "./screens/Recommendation.jsx";
import History from "./screens/History.jsx";
import { SproutIcon, LeafIcon, ChartIcon } from "./components/ui.jsx";

const ID_KEY = "farmsense_farmer_id";
const STAGE_KEY = "farmsense_stage";

export default function App() {
  const [farmerId, setFarmerId] = useState(() => localStorage.getItem(ID_KEY) || "");
  const [stage, setStage] = useState(() => {
    const savedId = localStorage.getItem(ID_KEY);
    const savedStage = localStorage.getItem(STAGE_KEY);
    return savedId && savedStage ? savedStage : "onboarding";
  });
  const [tab, setTab] = useState("advice");

  const goStage = (s) => {
    setStage(s);
    localStorage.setItem(STAGE_KEY, s);
    window.scrollTo({ top: 0 });
  };

  const handleProfileCreated = (id) => {
    localStorage.setItem(ID_KEY, id);
    setFarmerId(id);
    goStage("photo");
  };

  const handlePhotoDone = () => goStage("main");

  const startOver = () => {
    localStorage.removeItem(ID_KEY);
    localStorage.removeItem(STAGE_KEY);
    setFarmerId("");
    setStage("onboarding");
    setTab("advice");
    window.scrollTo({ top: 0 });
  };

  return (
    <div className="app">
      <Background />

      <div className="container">
        <header className="topbar">
          <div className="brand">
            <span className="brand-icon">
              <SproutIcon size={30} />
            </span>
            <span className="brand-name">FarmSense</span>
          </div>
          {stage !== "onboarding" && (
            <button type="button" className="link-btn" onClick={startOver}>
              Start over
            </button>
          )}
        </header>

        {stage === "onboarding" && <Onboarding onCreated={handleProfileCreated} />}

        {stage === "photo" && <PhotoUpload farmerId={farmerId} onDone={handlePhotoDone} />}

        {stage === "main" && (
          <>
            {tab === "advice" ? (
              <Recommendation farmerId={farmerId} />
            ) : (
              <History farmerId={farmerId} />
            )}

            <nav className="tabbar" aria-label="Main navigation">
              <div className="tabbar-inner glass">
                <button
                  type="button"
                  className={`tab ${tab === "advice" ? "active" : ""}`}
                  onClick={() => setTab("advice")}
                >
                  <LeafIcon size={22} />
                  <span>Advice</span>
                </button>
                <button
                  type="button"
                  className={`tab ${tab === "history" ? "active" : ""}`}
                  onClick={() => setTab("history")}
                >
                  <ChartIcon size={22} />
                  <span>History</span>
                </button>
              </div>
            </nav>
          </>
        )}
      </div>
    </div>
  );
}
