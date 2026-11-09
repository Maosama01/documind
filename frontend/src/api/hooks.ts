import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage, unwrap, type Document } from "./client";

export const keys = {
  me: ["me"] as const,
  documents: ["documents"] as const,
  document: (id: number) => ["documents", id] as const,
  pdf: (id: number) => ["pdf", id] as const,
};

/** pending and processing change on their own; processed and failed do not. */
export const isInProgress = (status: string) => status === "pending" || status === "processing";
const POLL_MS = 2000;

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: async () => unwrap(await api.GET("/auth/me")),
    staleTime: 5 * 60_000,
  });
}

export function useDocuments() {
  return useQuery({
    queryKey: keys.documents,
    queryFn: async () => unwrap(await api.GET("/documents/")),
    // Keep refreshing only while something is still being read.
    refetchInterval: (query) =>
      query.state.data?.documents.some((d) => isInProgress(d.status)) ? POLL_MS : false,
  });
}

export function useDocument(id: number) {
  return useQuery({
    queryKey: keys.document(id),
    queryFn: async () =>
      unwrap(await api.GET("/documents/{document_id}", { params: { path: { document_id: id } } })),
    refetchInterval: (query) => (query.state.data && isInProgress(query.state.data.status) ? POLL_MS : false),
  });
}

export function useUpload() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (file: File): Promise<Document> =>
      unwrap(
        await api.POST("/documents/upload", {
          body: { file: file as unknown as string },
          bodySerializer: (body) => {
            const form = new FormData();
            form.append("file", body.file as unknown as Blob);
            return form;
          },
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.documents }),
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => {
      const { error, response } = await api.DELETE("/documents/{document_id}", {
        params: { path: { document_id: id } },
      });
      if (error !== undefined || !response.ok) throw new Error(errorMessage(error, "Couldn't delete the document."));
      return id;
    },
    onSuccess: (id) => {
      queryClient.removeQueries({ queryKey: keys.document(id) });
      queryClient.removeQueries({ queryKey: keys.pdf(id) });
      return queryClient.invalidateQueries({ queryKey: keys.documents });
    },
  });
}

export function useAsk() {
  return useMutation({
    mutationFn: async (input: { documentId: number; question: string; maxResults: number }) =>
      unwrap(
        await api.POST("/query/", {
          body: { document_id: input.documentId, question: input.question, max_results: input.maxResults },
        }),
      ),
  });
}

/** The document's PDF as an object URL for the viewer; revoked when no longer shown. */
export function usePdfUrl(id: number, enabled: boolean) {
  const blob = useQuery({
    queryKey: keys.pdf(id),
    enabled,
    staleTime: Infinity,
    queryFn: async () =>
      unwrap(
        await api.GET("/documents/{document_id}/file", {
          params: { path: { document_id: id } },
          parseAs: "blob",
        }),
      ) as Blob,
  });
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!blob.data) return;
    const objectUrl = URL.createObjectURL(blob.data);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [blob.data]);
  return { url, isLoading: blob.isLoading, error: blob.error, refetch: blob.refetch };
}
