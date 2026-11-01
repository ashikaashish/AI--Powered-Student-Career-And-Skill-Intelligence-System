import { useCallback, useEffect, useRef, useState } from "react";
import client from "../api/client";

// Events that count as warnings (must match VIOLATION_TYPES in routes/assessment.py)
const VIOLATIONS = new Set(["tab_switch", "fullscreen_exit", "no_face", "multiple_faces"]);

const LABELS = {
  session_start: "Assessment started",
  camera_on: "Camera on",
  camera_denied: "Camera not available",
  face_model_unavailable: "Face check unavailable",
  tab_switch: "Tab switch detected",
  fullscreen_exit: "Left full screen",
  no_face: "No face visible",
  multiple_faces: "More than one face",
  copy_blocked: "Copy blocked",
  paste_blocked: "Paste blocked",
  menu_blocked: "Right-click blocked",
  auto_submit: "Auto-submitted",
};

const MP_WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm";
const MP_MODEL =
  "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";

const NO_FACE_SECONDS = 5;   // face missing this long -> warning
const MULTI_FACE_SECONDS = 3; // 2+ faces this long   -> warning

/**
 * Light proctoring for one assessment sitting.
 *  - tab switch + fullscreen exit + copy/paste/right-click blocking
 *  - optional webcam with in-browser face detection (no video ever leaves the browser)
 * Every event is reported to the server, which keeps the official violation count.
 */
export default function useProctoring({ courseId, sessionId, active, maxViolations, onTerminate }) {
  const [cameraState, setCameraState] = useState("off");   // off | on | denied
  const [faceState, setFaceState] = useState("unknown");   // unknown | ok | none | multiple | unavailable
  const [violations, setViolations] = useState(0);
  const [log, setLog] = useState([]);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const stoppedRef = useRef(false);
  const terminatedRef = useRef(false);
  const lastViolationAt = useRef(0);
  const onTerminateRef = useRef(onTerminate);
  const logEventRef = useRef(() => {});

  useEffect(() => { onTerminateRef.current = onTerminate; });

  // A new session = a fresh start
  useEffect(() => {
    stoppedRef.current = false;
    terminatedRef.current = false;
    lastViolationAt.current = 0;
    setViolations(0);
    setLog([]);
  }, [sessionId]);

  const logEvent = useCallback((type, detail = "") => {
    if (stoppedRef.current || !sessionId) return;
    const isViolation = VIOLATIONS.has(type);
    if (isViolation) {
      // One real-world action (e.g. alt-tab) often fires 2 browser events; count it once.
      const now = Date.now();
      if (now - lastViolationAt.current < 1500) return;
      lastViolationAt.current = now;
    }
    setLog((l) => [{ time: new Date(), type, label: LABELS[type] || type, bad: isViolation }, ...l].slice(0, 50));
    client
      .post(`/assessment/${courseId}/proctor-event`, { session_id: sessionId, event_type: type, detail })
      .then((res) => {
        setViolations(res.data.violations);
        if (res.data.violations >= maxViolations && !terminatedRef.current) {
          terminatedRef.current = true;
          onTerminateRef.current?.();
        }
      })
      .catch(() => {});
  }, [courseId, sessionId, maxViolations]);

  useEffect(() => { logEventRef.current = logEvent; }, [logEvent]);

  // ---- camera ----
  const startCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(() => {});
      }
      setCameraState("on");
      return true;
    } catch {
      setCameraState("denied");
      return false;
    }
  }, []);

  // Use as <video ref={attachVideo} />; works even if the stream starts before the element exists.
  const attachVideo = useCallback((el) => {
    videoRef.current = el;
    if (el && streamRef.current) {
      el.srcObject = streamRef.current;
      el.play().catch(() => {});
    }
  }, []);

  // ---- fullscreen ----
  const enterFullscreen = useCallback(() => {
    const el = document.documentElement;
    if (!el.requestFullscreen) return Promise.resolve(false);
    return el.requestFullscreen().then(() => true).catch(() => false);
  }, []);

  // ---- browser listeners (only while the quiz is running) ----
  useEffect(() => {
    if (!active) return;
    setIsFullscreen(!!document.fullscreenElement);

    const onVisibility = () => { if (document.hidden) logEventRef.current("tab_switch"); };
    const onFullscreen = () => {
      const fs = !!document.fullscreenElement;
      setIsFullscreen(fs);
      if (!fs) logEventRef.current("fullscreen_exit");
    };
    const onBlock = (e) => {
      e.preventDefault();
      logEventRef.current(e.type === "paste" ? "paste_blocked" : e.type === "contextmenu" ? "menu_blocked" : "copy_blocked");
    };

    document.addEventListener("visibilitychange", onVisibility);
    document.addEventListener("fullscreenchange", onFullscreen);
    ["copy", "cut", "paste", "contextmenu"].forEach((t) => document.addEventListener(t, onBlock));
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("fullscreenchange", onFullscreen);
      ["copy", "cut", "paste", "contextmenu"].forEach((t) => document.removeEventListener(t, onBlock));
    };
  }, [active]);

  // ---- camera events + face detection ----
  useEffect(() => {
    if (!active) return;
    if (cameraState === "on") logEventRef.current("camera_on");
    if (cameraState === "denied") logEventRef.current("camera_denied");
  }, [active, cameraState]);

  useEffect(() => {
    if (!active || cameraState !== "on") return;
    let cancelled = false;
    let timer = null;
    let detector = null;
    let noFace = 0;
    let multi = 0;

    (async () => {
      try {
        const { FaceDetector, FilesetResolver } = await import("@mediapipe/tasks-vision");
        const fileset = await FilesetResolver.forVisionTasks(MP_WASM);
        detector = await FaceDetector.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MP_MODEL },
          runningMode: "VIDEO",
          minDetectionConfidence: 0.5,
        });
        if (cancelled) { detector.close(); return; }

        timer = setInterval(() => {
          const v = videoRef.current;
          if (!v || v.readyState < 2) return;
          const n = detector.detectForVideo(v, performance.now()).detections.length;
          if (n === 1) { noFace = 0; multi = 0; setFaceState("ok"); }
          else if (n === 0) {
            multi = 0; noFace += 1; setFaceState("none");
            if (noFace >= NO_FACE_SECONDS) { noFace = 0; logEventRef.current("no_face"); }
          } else {
            noFace = 0; multi += 1; setFaceState("multiple");
            if (multi >= MULTI_FACE_SECONDS) { multi = 0; logEventRef.current("multiple_faces"); }
          }
        }, 1000);
      } catch {
        // Offline / blocked CDN / old browser: the quiz still works, just without the face check.
        if (!cancelled) { setFaceState("unavailable"); logEventRef.current("face_model_unavailable"); }
      }
    })();

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
      try { detector?.close(); } catch { /* already closed */ }
    };
  }, [active, cameraState]);

  // ---- call when the quiz is finished ----
  const stop = useCallback(() => {
    stoppedRef.current = true;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraState("off");
    setFaceState("unknown");
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  }, []);

  // Release the camera if the student navigates away
  useEffect(() => () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
  }, []);

  return {
    attachVideo, cameraState, faceState, violations, log, isFullscreen,
    startCamera, enterFullscreen, stop, logEvent,
  };
}