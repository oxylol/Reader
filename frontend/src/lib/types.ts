export interface User {
  id: number;
  username: string;
  is_admin: boolean;
}

export interface Series {
  id: number;
  source: string;
  source_id: string;
  slug: string;
  title: string;
  cover_url: string;
  type: string;
  status: string;
  description: string;
  tags: string[];
  year: number | null;
  content_rating: string;
  default_mode: string;
  in_library: boolean;
  chapter_count: number;
  downloaded_count: number;
  unread_count: number;
}

export interface Chapter {
  id: number;
  number: number;
  number_label: string;
  volume: string;
  title: string;
  language: string;
  scanlation_group: string;
  page_count: number;
  downloaded: boolean;
  size_bytes: number;
  read: boolean;
  current_page: number;
}

export interface DiscoverItem {
  source: string;
  source_id: string;
  slug: string;
  title: string;
  cover_url: string;
  type: string;
  status: string;
  description: string;
  tags: string[];
  year: number | null;
  rating: number | null;
  follow_count: number | null;
  in_library: boolean;
  sources: string[];
}

export interface Job {
  id: number;
  series_id: number;
  state: string;
  total_chapters: number;
  done_chapters: number;
  failed_chapters: number;
  message: string;
}

export interface Prefs {
  reading_mode: string;
  rtl: boolean;
  fit: string;
  theme: string;
  double_page: boolean;
}

export interface ChapterInfo {
  chapter: Chapter;
  series_id: number;
  series_title: string;
  series_type: string;
  default_mode: string;
  page_count: number;
  prev_chapter_id: number | null;
  next_chapter_id: number | null;
}

export interface ContinueItem {
  series: Series;
  chapter: Chapter;
  page: number;
  scroll: number;
}

export interface SourceInfo {
  key: string;
  name: string;
  needs_cloudflare: boolean;
  supports_trending: boolean;
  supports_advanced_search: boolean;
}

export interface SearchRequest {
  query?: string;
  include_tags?: string[];
  exclude_tags?: string[];
  types?: string[];
  status?: string[];
  original_language?: string[];
  translated_language?: string[];
  year_from?: number | null;
  year_to?: number | null;
  content_rating?: string[];
  scanlation_group?: string;
  sort?: string;
  sources?: string[];
  page?: number;
  limit?: number;
}

export interface StorageStats {
  total_bytes: number;
  series_count: number;
  chapter_count: number;
  series: {
    series_id: number;
    title: string;
    size_bytes: number;
    chapter_count: number;
  }[];
}
