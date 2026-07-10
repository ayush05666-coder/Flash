import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Client-Info, Apikey",
};

// ── Platform detection ────────────────────────────────────────────────────────
function detectPlatform(url: string): string {
  if (/youtube\.com\/watch|youtu\.be\//.test(url)) return "youtube";
  if (/youtube\.com\/(shorts|live)/.test(url)) return "youtube";
  if (/vimeo\.com\/\d/.test(url)) return "vimeo";
  if (/twitter\.com|x\.com/.test(url)) return "twitter";
  if (/tiktok\.com/.test(url)) return "tiktok";
  if (/instagram\.com\/(p|reel|tv)/.test(url)) return "instagram";
  if (/twitch\.tv/.test(url)) return "twitch";
  if (/soundcloud\.com/.test(url)) return "soundcloud";
  if (/reddit\.com\/r\/.+\/comments/.test(url)) return "reddit";
  if (/facebook\.com|fb\.watch/.test(url)) return "facebook";
  if (/dailymotion\.com/.test(url)) return "dailymotion";
  if (/bilibili\.com/.test(url)) return "bilibili";
  if (/twitch\.tv/.test(url)) return "twitch";
  if (/streamable\.com/.test(url)) return "streamable";
  return "generic";
}

// ── YouTube video ID extraction ───────────────────────────────────────────────
function getYouTubeId(url: string): string | null {
  const m =
    url.match(/[?&]v=([a-zA-Z0-9_-]{11})/) ||
    url.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/) ||
    url.match(/\/shorts\/([a-zA-Z0-9_-]{11})/) ||
    url.match(/\/live\/([a-zA-Z0-9_-]{11})/);
  return m ? m[1] : null;
}

// ── oEmbed fetch (YouTube, Vimeo, Twitter, TikTok, etc.) ─────────────────────
async function fetchOEmbed(url: string): Promise<Record<string, unknown> | null> {
  const endpoints = [
    `https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`,
    `https://vimeo.com/api/oembed.json?url=${encodeURIComponent(url)}`,
    `https://publish.twitter.com/oembed?url=${encodeURIComponent(url)}`,
    `https://www.tiktok.com/oembed?url=${encodeURIComponent(url)}`,
    `https://noembed.com/embed?url=${encodeURIComponent(url)}`,
  ];

  for (const ep of endpoints) {
    try {
      const r = await fetch(ep, {
        headers: { "User-Agent": "FlashMedia/2.0" },
        signal: AbortSignal.timeout(8000),
      });
      if (r.ok) {
        const data = await r.json();
        if (data && (data.title || data.author_name)) return data;
      }
    } catch {
      // try next endpoint
    }
  }
  return null;
}

// ── YouTube thumbnail URL variants ───────────────────────────────────────────
function ytThumb(id: string): string {
  return `https://img.youtube.com/vi/${id}/maxresdefault.jpg`;
}

// ── Build format list based on platform ──────────────────────────────────────
function buildFormats(platform: string, hasVideo: boolean): Format[] {
  if (!hasVideo || platform === "soundcloud") {
    return [
      { label: "Best Audio (MP3 320kbps)", formatId: "bestaudio/best", isAudioOnly: true, needsMerge: false, ext: "mp3", fileSizeApprox: null, quality: "audio", badge: "MP3" },
      { label: "Best Audio (M4A 256kbps)", formatId: "bestaudio[ext=m4a]", isAudioOnly: true, needsMerge: false, ext: "m4a", fileSizeApprox: null, quality: "audio", badge: "M4A" },
    ];
  }

  const base: Format[] = [
    {
      label: "Best Quality (Auto)",
      formatId: "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
      isAudioOnly: false, needsMerge: true, ext: "mp4",
      fileSizeApprox: null, quality: "best", badge: "BEST",
    },
  ];

  if (platform === "youtube") {
    base.push(
      { label: "4K Ultra HD (2160p)", formatId: "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/best[height<=2160]", isAudioOnly: false, needsMerge: true, ext: "mp4", fileSizeApprox: 4_800_000_000, quality: "2160p", badge: "4K" },
      { label: "2K QHD (1440p)",      formatId: "bestvideo[height<=1440][ext=mp4]+bestaudio[ext=m4a]/best[height<=1440]", isAudioOnly: false, needsMerge: true, ext: "mp4", fileSizeApprox: 2_100_000_000, quality: "1440p", badge: "2K" },
      { label: "Full HD (1080p)",     formatId: "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]", isAudioOnly: false, needsMerge: true, ext: "mp4", fileSizeApprox: 1_100_000_000, quality: "1080p", badge: "FHD" },
      { label: "HD (720p)",           formatId: "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]",   isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: 380_000_000, quality: "720p", badge: "HD" },
      { label: "SD (480p)",           formatId: "best[height<=480][ext=mp4]/best[height<=480]",    isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: 130_000_000, quality: "480p", badge: "SD" },
      { label: "Low (360p)",          formatId: "best[height<=360][ext=mp4]/best[height<=360]",    isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox:  65_000_000, quality: "360p", badge: "360" },
      { label: "Mobile (240p)",       formatId: "best[height<=240]",                               isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox:  28_000_000, quality: "240p", badge: "240" },
    );
  } else if (platform === "vimeo") {
    base.push(
      { label: "4K (2160p)", formatId: "bestvideo[height<=2160]+bestaudio/best", isAudioOnly: false, needsMerge: true,  ext: "mp4", fileSizeApprox: 3_500_000_000, quality: "2160p", badge: "4K" },
      { label: "HD (1080p)", formatId: "bestvideo[height<=1080]+bestaudio/best", isAudioOnly: false, needsMerge: true,  ext: "mp4", fileSizeApprox:   900_000_000, quality: "1080p", badge: "FHD" },
      { label: "HD (720p)",  formatId: "bestvideo[height<=720]+bestaudio/best",  isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox:   300_000_000, quality: "720p",  badge: "HD" },
      { label: "SD (480p)",  formatId: "best[height<=480]",                      isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox:   100_000_000, quality: "480p",  badge: "SD" },
      { label: "SD (360p)",  formatId: "best[height<=360]",                      isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox:    50_000_000, quality: "360p",  badge: "360" },
    );
  } else if (platform === "twitter" || platform === "tiktok" || platform === "instagram") {
    base.push(
      { label: "Highest Quality",  formatId: "bestvideo+bestaudio/best", isAudioOnly: false, needsMerge: true,  ext: "mp4", fileSizeApprox: null, quality: "high", badge: "HD" },
      { label: "Medium Quality",   formatId: "best[height<=720]",        isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: null, quality: "720p", badge: "720" },
      { label: "Standard Quality", formatId: "best[height<=480]",        isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: null, quality: "480p", badge: "480" },
    );
  } else if (platform === "twitch") {
    base.push(
      { label: "Source Quality",  formatId: "best",              isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: null, quality: "source", badge: "SRC" },
      { label: "1080p60",         formatId: "best[height<=1080]", isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: null, quality: "1080p",  badge: "FHD" },
      { label: "720p60",          formatId: "best[height<=720]",  isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: null, quality: "720p",   badge: "HD" },
      { label: "480p",            formatId: "best[height<=480]",  isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: null, quality: "480p",   badge: "SD" },
    );
  } else {
    base.push(
      { label: "High Quality (1080p)", formatId: "bestvideo[height<=1080]+bestaudio/best", isAudioOnly: false, needsMerge: true,  ext: "mp4", fileSizeApprox: null, quality: "1080p", badge: "FHD" },
      { label: "HD (720p)",            formatId: "bestvideo[height<=720]+bestaudio/best",  isAudioOnly: false, needsMerge: true,  ext: "mp4", fileSizeApprox: null, quality: "720p",  badge: "HD" },
      { label: "Standard (480p)",      formatId: "best[height<=480]",                      isAudioOnly: false, needsMerge: false, ext: "mp4", fileSizeApprox: null, quality: "480p",  badge: "SD" },
    );
  }

  // Audio always at the bottom
  base.push(
    { label: "Audio Only (MP3 320kbps)", formatId: "bestaudio/best", isAudioOnly: true, needsMerge: false, ext: "mp3", fileSizeApprox: null, quality: "audio", badge: "MP3" },
    { label: "Audio Only (M4A 256kbps)", formatId: "bestaudio[ext=m4a]/bestaudio", isAudioOnly: true, needsMerge: false, ext: "m4a", fileSizeApprox: null, quality: "audio", badge: "M4A" },
  );

  return base;
}

interface Format {
  label: string;
  formatId: string;
  isAudioOnly: boolean;
  needsMerge: boolean;
  ext: string;
  fileSizeApprox: number | null;
  quality: string;
  badge: string;
}

// ── Main handler ──────────────────────────────────────────────────────────────
Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 200, headers: corsHeaders });
  }

  try {
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method not allowed" }), {
        status: 405, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const body = await req.json().catch(() => ({}));
    const url: string = (body.url ?? "").trim();

    if (!url) {
      return new Response(JSON.stringify({ error: "url is required" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Validate URL shape
    let parsed: URL;
    try {
      parsed = new URL(url);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error();
    } catch {
      return new Response(JSON.stringify({ error: "Invalid URL — must be http or https" }), {
        status: 422, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const platform = detectPlatform(url);
    const ytId = getYouTubeId(url);

    // Fetch real metadata via oEmbed
    const oembed = await fetchOEmbed(url);

    // Build title
    let title = oembed?.title as string || "";
    let uploader = (oembed?.author_name as string) || "";
    let thumbnailUrl = (oembed?.thumbnail_url as string) || "";
    let duration = 0;

    // YouTube-specific thumbnail upgrade
    if (platform === "youtube" && ytId) {
      thumbnailUrl = ytThumb(ytId);
      // Try to get duration from YouTube's oEmbed (not included, but some
      // thumbnail services return it). Fall back to a reasonable unknown.
      duration = 0; // duration not available in oEmbed v1
    }

    // Vimeo oEmbed includes duration
    if (platform === "vimeo" && oembed?.duration) {
      duration = Number(oembed.duration) || 0;
    }

    // If oEmbed failed, build a fallback title from the URL path
    if (!title) {
      const pathParts = parsed.pathname.split("/").filter(Boolean);
      title = pathParts[pathParts.length - 1]?.replace(/[-_]/g, " ") || parsed.hostname;
    }

    const isAudioPlatform = platform === "soundcloud";
    const formats = buildFormats(platform, !isAudioPlatform);

    const result = {
      title,
      duration,
      thumbnailUrl,
      uploader,
      webpageUrl: url,
      platform,
      streams: formats,
    };

    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (err) {
    const message = err instanceof Error ? err.message : "Internal server error";
    return new Response(JSON.stringify({ error: message }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
