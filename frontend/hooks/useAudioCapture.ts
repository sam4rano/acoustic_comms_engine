"use client";

import { useRef, useCallback, useState } from "react";
import { AudioEncoder } from "@/lib/audio-encoder";

export function useAudioCapture() {
  const streamRef = useRef<MediaStream | null>(null);
  const encoderRef = useRef(new AudioEncoder());
  const [isCapturing, setIsCapturing] = useState(false);

  const startCapture = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;
      setIsCapturing(true);
      return stream;
    } catch (err) {
      console.error("Audio capture failed:", err);
      throw err;
    }
  }, []);

  const stopCapture = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    encoderRef.current.reset();
    setIsCapturing(false);
  }, []);

  return { isCapturing, startCapture, stopCapture, encoder: encoderRef.current };
}
