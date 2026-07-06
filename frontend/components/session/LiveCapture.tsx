"use client";

import { useCallback } from "react";
import { Mic, MicOff } from "lucide-react";
import { useAudioCapture } from "@/hooks/useAudioCapture";

interface LiveCaptureProps {
  onStream: (stream: MediaStream) => void;
  onStop: () => void;
}

export function LiveCapture({ onStream, onStop }: LiveCaptureProps) {
  const { isCapturing, startCapture, stopCapture } = useAudioCapture();

  const handleToggle = useCallback(async () => {
    if (isCapturing) {
      stopCapture();
      onStop();
    } else {
      const stream = await startCapture();
      onStream(stream);
    }
  }, [isCapturing, startCapture, stopCapture, onStream, onStop]);

  return (
    <button
      type="button"
      onClick={handleToggle}
      className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-colors ${
        isCapturing
          ? "bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-300"
          : "bg-teal-100 text-teal-700 hover:bg-teal-200 dark:bg-teal-900/30 dark:text-teal-300"
      }`}
    >
      {isCapturing ? <MicOff className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
      {isCapturing ? "Stop Capture" : "Start Capture"}
    </button>
  );
}
