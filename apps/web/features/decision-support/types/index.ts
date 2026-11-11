export type Product = {
  id: number; category_key: string; brand: string; model: string; variant: string;
  specs: Record<string, string>; review_count: number; average_rating: number | null;
  latest_price: number | null; currency: string | null; price_observed_at: string | null;
};

export type ImportPreview = {
  source_name: string; rows_seen: number; accepted: number; duplicates: number;
  rejected: number; distinct_products: number;
  rows: { line: number; status: string; reason: string }[];
};

export type RankingItem = {
  rank: number; id: number; brand: string; model: string; variant: string; score: number;
  coverage: number; missing_criteria: string[]; contributions: Record<string, number>;
  price: number | null; currency: string | null; price_observed_at: string | null;
  review_count: number; average_rating: number | null;
};

export type ProductDetail = Product & {
  specification_sources: { attribute_key: string; value: string; source_name: string; source_url: string; observed_at: string }[];
  prices: { source_name: string; price: number; currency: string; observed_at: string; source_url: string }[];
  reviews: { id: number; source_name: string; source_url: string; text: string; rating: number | null; review_date: string }[];
  aspect_insights: { aspect_key: string; sentiment: string; evidence_count: number; confidence: number }[];
};

export type ModelStatus = {
  ready: boolean;
  evaluation: { macro_f1: number } | null;
  message?: string;
};
