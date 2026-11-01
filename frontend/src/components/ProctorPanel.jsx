import { AlertTriangle, CheckCircle2, Clock, Eye, Maximize, User, VideoOff } from "lucide-react";
import { Card } from "./Layout";

const FACE_TEXT = {
  unknown: "Starting face check…",
  ok: "Face detected",
  none: "No face visible",
  multiple: "More than one face",
  unavailable: "Face check unavailable",
};

function mmss(total) {
  const m = String(Math.floor(total / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function Row({ ok, icon: Icon, children }) {
  return (
    <div className="flex items-center gap-2 text-xs text-slate-700">
      <Icon size={14} className={ok ? "text-teal-600" : "text-amber-600"} />
      <span>{children}</span>
    </div>
  );
}

export default function ProctorPanel({ proctor, secondsLeft, maxViolations, onReturnFullscreen }) {
  const { attachVideo, cameraState, faceState, violations, log, isFullscreen } = proctor;
  const cameraOn = cameraState === "on";
  const lowTime = secondsLeft <= 60;

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-bold text-slate-800 flex items-center gap-1.5"><Eye size={15} className="text-primary-600" /> Proctoring</p>
          <span className="text-[10px] font-bold text-white bg-teal-600 rounded px-1.5 py-0.5">LIVE</span>
        </div>

        <div className="rounded-lg overflow-hidden bg-slate-100 aspect-[4/3] flex items-center justify-center mb-3">
          {cameraOn ? (
            <video ref={attachVideo} muted playsInline className="w-full h-full object-cover scale-x-[-1]" />
          ) : (
            <div className="text-center text-slate-400 text-xs px-3">
              <VideoOff size={22} className="mx-auto mb-1" />
              {cameraState === "denied" ? "Camera not allowed. Only tab and full-screen checks are active." : "Camera off"}
            </div>
          )}
        </div>

        <div className="space-y-1.5">
          <Row ok icon={Clock}>
            <span className={`font-mono font-semibold ${lowTime ? "text-red-600" : ""}`}>{mmss(secondsLeft)}</span> left
          </Row>
          {cameraOn && (
            <Row ok={faceState === "ok" || faceState === "unknown" || faceState === "unavailable"} icon={User}>
              {FACE_TEXT[faceState]}
            </Row>
          )}
          <Row ok={isFullscreen} icon={Maximize}>{isFullscreen ? "Full screen" : "Not in full screen"}</Row>
          <Row ok={violations === 0} icon={violations === 0 ? CheckCircle2 : AlertTriangle}>
            Warnings: {violations} / {maxViolations}
          </Row>
        </div>

        {!isFullscreen && (
          <button onClick={onReturnFullscreen} className="mt-3 w-full text-xs font-semibold text-primary-700 bg-primary-50 hover:bg-primary-100 rounded-lg py-2">
            Return to full screen
          </button>
        )}
      </Card>

      <Card>
        <p className="text-sm font-bold text-slate-800 mb-2">Activity log</p>
        {log.length === 0 ? (
          <p className="text-xs text-slate-400">Nothing yet.</p>
        ) : (
          <ul className="space-y-1.5 max-h-48 overflow-y-auto">
            {log.map((e, i) => (
              <li key={i} className={`flex items-center justify-between gap-2 text-xs ${e.bad ? "text-red-600" : "text-slate-600"}`}>
                <span className="flex items-center gap-1.5">
                  {e.bad ? <AlertTriangle size={12} /> : <CheckCircle2 size={12} className="text-teal-600" />}
                  {e.label}
                </span>
                <span className="text-slate-400 shrink-0">{e.time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}