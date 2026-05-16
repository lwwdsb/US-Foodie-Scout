"use client";
import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";

const SESSION_KEY = "foodie_scout_session_id";

export function useSession() {
  const [sessionId, setSessionId] = useState<string>("");

  useEffect(() => {
    let id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = uuidv4();
      localStorage.setItem(SESSION_KEY, id);
    }
    setSessionId(id);
  }, []);

  const resetSession = () => {
    const id = uuidv4();
    localStorage.setItem(SESSION_KEY, id);
    setSessionId(id);
  };

  return { sessionId, resetSession };
}
