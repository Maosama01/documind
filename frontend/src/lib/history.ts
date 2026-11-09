import { useCallback, useEffect, useState } from "react";
import type { QueryResult } from "../api/client";

// The API does not store questions or answers. A document's questions are
// kept in this browser tab only (sessionStorage): they survive a reload and
// are gone when the tab closes or the user signs out.

export type Turn = {
  id: string;
  question: string;
  maxResults: number;
  askedAt: string;
  status: "pending" | "done" | "error";
  result?: QueryResult;
  error?: string;
};

const key = (documentId: number) => `documind.history.${documentId}`;

function load(documentId: number): Turn[] {
  try {
    const raw = window.sessionStorage.getItem(key(documentId));
    const turns = raw ? (JSON.parse(raw) as Turn[]) : [];
    // A question still pending when the page was left never got its answer.
    return turns.map((turn) =>
      turn.status === "pending" ? { ...turn, status: "error", error: "The page was reloaded before the answer arrived." } : turn,
    );
  } catch {
    return [];
  }
}

export function useHistory(documentId: number) {
  const [turns, setTurns] = useState<Turn[]>(() => load(documentId));

  useEffect(() => setTurns(load(documentId)), [documentId]);
  useEffect(() => {
    try {
      window.sessionStorage.setItem(key(documentId), JSON.stringify(turns));
    } catch {
      // storage full or blocked: the history lasts until the page is left
    }
  }, [documentId, turns]);

  const add = useCallback((turn: Turn) => setTurns((current) => [turn, ...current]), []);
  const update = useCallback(
    (id: string, change: Partial<Turn>) =>
      setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, ...change } : turn))),
    [],
  );
  return { turns, add, update };
}
