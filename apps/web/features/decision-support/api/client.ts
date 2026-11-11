import type { ImportPreview, ModelStatus, Product, ProductDetail, RankingItem } from "../types";

const API = process.env.NODE_ENV === "development" ? "http://127.0.0.1:7860" : "";
const ROOT = "/api/v1/decision-support";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + ROOT + path, init);
  const value = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(value.detail || "Permintaan gagal.");
  return value as T;
}

function upload(file: File) {
  const form = new FormData();
  form.append("file", file);
  return form;
}

export const listProducts = (search: string) =>
  request<{ products: Product[] }>(`/products?${new URLSearchParams({ category: "tws", search })}`, { cache: "no-store" });

export const getProduct = (id: number) => request<ProductDetail>(`/products/${id}`, { cache: "no-store" });
export const getModelStatus = () => request<ModelStatus>("/model");

export const previewImport = (file: File) =>
  request<ImportPreview>("/imports/preview", { method: "POST", body: upload(file) });

export const commitImport = (file: File) =>
  request<{ products_added: number; reviews_added: number; prices_added: number }>("/imports", { method: "POST", body: upload(file) });

export const createRecommendations = (budget_max: number | null, weights: Record<string, number>) =>
  request<{ items: RankingItem[]; message?: string; policy?: string }>("/recommendations", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category: "tws", budget_max, weights }),
  });

export const analyzeReviews = () =>
  request<{ reviews_analyzed: number; aspect_predictions: number }>("/analyze", { method: "POST" });
